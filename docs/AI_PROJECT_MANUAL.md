# WolfyStock AI Project Manual

> GENERATED FILE. DO NOT EDIT DIRECTLY.
>
> Edit source docs or `scripts/build_ai_project_manual.py`, then run `python scripts/build_ai_project_manual.py`.

Status: generated AI maintenance onboarding manual.
Audience: Codex workers, review agents, integrators, and humans assigning AI work.
Authority: navigation and operating guide only; `AGENTS.md` remains the repository AI-collaboration source of truth.
Do not use as: launch approval, protected-domain authorization, stale audit authority, or replacement for current source/test inspection.

## Table Of Contents

- [Start Here: Authority And Operating Posture](#start-here-authority-and-operating-posture)
- [Product Purpose And Current Deployment Boundary](#product-purpose-and-current-deployment-boundary)
- [Architecture And Major Surfaces](#architecture-and-major-surfaces)
- [Auth, RBAC, And MFA](#auth-rbac-and-mfa)
- [Portfolio And Backtest](#portfolio-and-backtest)
- [Provider, Quota, And Cost](#provider-quota-and-cost)
- [WS2 And Durable Runtime](#ws2-and-durable-runtime)
- [Options And Data Pipeline](#options-and-data-pipeline)
- [Frontend IA And UI Conventions](#frontend-ia-and-ui-conventions)
- [Validation Profiles And Task Workflow](#validation-profiles-and-task-workflow)
- [Public Launch NO-GO Blockers](#public-launch-nogo-blockers)
- [Known Experimental And Demo-Only Surfaces](#known-experimental-and-demoonly-surfaces)
- [Source Inclusion And Exclusion Policy](#source-inclusion-and-exclusion-policy)
- [Source Map](#source-map)
- [JSON Manifest](#json-manifest)

## Start Here: Authority And Operating Posture

Use this generated manual as the first navigation layer for AI-assisted work. It is not a new rule source and does not replace current source inspection, tests, or task-specific prompt boundaries.

- Current user prompts and explicit allowed/forbidden diffs come first.
- `AGENTS.md` remains the repository AI-collaboration source of truth.
- Current code, scripts, tests, and active docs beat memory, stale screenshots, old audits, and generated artifacts.
- If a task is near protected semantics, stop unless the prompt explicitly scopes that domain and gives a validation path.
- Read-only tasks mean no edits, no artifacts, no staging, no commits, and no pushes.

Source provenance: [`AGENTS.md`](../AGENTS.md), [`docs/DOCS_INDEX.md`](DOCS_INDEX.md), [`docs/WOLFYSTOCK_AI_MAINTENANCE_MANUAL.md`](WOLFYSTOCK_AI_MAINTENANCE_MANUAL.md), [`docs/architecture/file-governance-taxonomy.md`](architecture/file-governance-taxonomy.md).

## Product Purpose And Current Deployment Boundary

WolfyStock is a professional financial research terminal. It combines market overview, scanner discovery, watchlists, rule backtesting, portfolio tracking, AI-assisted analysis, provider diagnostics, and admin observability.

It is not a broker, order-entry surface, generic retail trading app, or unbounded LLM wrapper. Public launch remains NO-GO until security, provider/data, WS2, cost/quota, portfolio/backtest safety, and deployment evidence gates are accepted. Treat private-beta and local tooling as reviewed integration surfaces, not launch approval.

Current safe posture is analytical and no-advice. Do not add buy/sell/order affordances, broker execution, or personalized financial advice unless a separate safety-reviewed task explicitly scopes that change.

Source provenance: [`README.md`](../README.md), [`docs/WOLFYSTOCK_SYSTEM_HANDBOOK.md`](WOLFYSTOCK_SYSTEM_HANDBOOK.md), [`docs/DEPLOY.md`](DEPLOY.md), [`docs/audits/private-beta-readiness.md`](audits/private-beta-readiness.md), [`docs/audits/public-launch-readiness-master.md`](audits/public-launch-readiness-master.md), [`docs/audits/trading-no-advice-product-policy.md`](audits/trading-no-advice-product-policy.md).

## Architecture And Major Surfaces

Maintain WolfyStock as bounded-context modules with narrow public interfaces. Consumers should call facades, schemas, DTOs, API clients, validators, and documented commands instead of private engines, repositories, provider clients, cache keys, or mutation internals.

Major runtime surfaces are `main.py`, `server.py`, `api/app.py`, `api/v1/router.py`, `src/services/`, `src/repositories/`, `data_provider/`, `apps/dsa-web/`, `apps/dsa-desktop/`, `scripts/`, and `.github/workflows/`.

Main product routes include Home, Scanner, Watchlist, Market Overview, Liquidity Monitor, Rotation Radar, Portfolio, Backtest, Options Lab, Settings, and Admin/Ops pages. API groups live under `/api/v1` for auth, analysis, history, stocks, backtest, scanner, system, usage, portfolio, watchlist, market, quant, options, and admin families.

Source provenance: [`docs/WOLFYSTOCK_SYSTEM_HANDBOOK.md`](WOLFYSTOCK_SYSTEM_HANDBOOK.md), [`docs/architecture/WOLFYSTOCK_MODULE_ARCHITECTURE.md`](architecture/WOLFYSTOCK_MODULE_ARCHITECTURE.md), [`docs/architecture/backend-frontend-modular-maintenance-handbook.md`](architecture/backend-frontend-modular-maintenance-handbook.md), [`README.md`](../README.md).

## Auth, RBAC, And MFA

Auth/RBAC/security is a protected domain. Do not alter dependencies, capabilities, admin route protection, session behavior, CSRF/CORS/security middleware, password/token handling, or MFA behavior as a side effect.

Current launch posture remains manual-review-gated. Production MFA secret custody/recovery, staged MFA enforcement, route/capability inventory, coarse fallback removal, role governance, and rollback evidence are not launch-accepted as broad public controls.

Security evidence must be sanitized. Never include raw cookies, Authorization headers, session IDs, request bodies, provider payloads, password hashes, or secret values in docs, logs, screenshots, reports, or release artifacts.

Source provenance: [`docs/audits/index-security-rbac-mfa.md`](audits/index-security-rbac-mfa.md), [`docs/audits/auth-rbac-release-security-guide.md`](audits/auth-rbac-release-security-guide.md), [`docs/audits/admin-rbac-r5-coarse-fallback-removal-plan.md`](audits/admin-rbac-r5-coarse-fallback-removal-plan.md), [`docs/audits/security-mfa-secret-storage-hardening-plan.md`](audits/security-mfa-secret-storage-hardening-plan.md), [`docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md`](codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md).

## Portfolio And Backtest

Portfolio owns accounts, holdings, cash, transactions, P&L, FX/native currency, cost basis, broker sync/import overlays, ledger mutations, and read projections. UI work must not recalculate accounting authority or imply broker order execution.

Backtest owns standard historical evaluation, deterministic rule backtests, calculation math, stored-first readback, support exports, compare workflows, universe diagnostics, and professional-readiness disclosures. The deterministic rule backtest lane is frozen as v1 semantics unless a future task explicitly versions and tests a new execution model.

Do not change portfolio accounting, mutation semantics, owner isolation, backtest fills, costs, metrics, benchmark semantics, stored-result authority, or local-only universe execution without explicit scope and focused regression evidence.

Source provenance: [`docs/portfolio/README.md`](portfolio/README.md), [`docs/backtest/README.md`](backtest/README.md), [`docs/backtest-system.md`](backtest-system.md), [`docs/audits/backtest-portfolio-public-safety-audit.md`](audits/backtest-portfolio-public-safety-audit.md), [`docs/codex/WOLFYSTOCK_BACKTEST_UNIVERSE_RULES.md`](codex/WOLFYSTOCK_BACKTEST_UNIVERSE_RULES.md).

## Provider, Quota, And Cost

Provider runtime owns provider order, fallback, retry/circuit posture, freshness labels, optional enrichment budgets, source disclosure, sanitized diagnostics, and cache/local-first behavior. Keep stale, fallback, mock, synthetic, fixture, repaired, or inferred data clearly not-live.

Quota and cost tooling is mostly advisory, dry-run, or pilot-bound unless a prompt explicitly scopes live route-boundary enforcement. Cost dashboards and ledgers are useful observability surfaces, but they are not billing-authoritative without accepted provider invoice/export reconciliation.

Do not reorder providers, deepen live fallback, add broad optional fanout, print raw provider payloads, or expose request URLs, headers, credentials, query strings, tokens, stack traces, or raw ledger internals.

Source provenance: [`docs/provider-data/README.md`](provider-data/README.md), [`docs/codex/WOLFYSTOCK_PROVIDER_BUDGET_AND_ROUTING_RULES.md`](codex/WOLFYSTOCK_PROVIDER_BUDGET_AND_ROUTING_RULES.md), [`docs/audits/index-provider-data-options.md`](audits/index-provider-data-options.md), [`docs/audits/index-cost-quota-observability.md`](audits/index-cost-quota-observability.md), [`docs/audits/quota-reserve-release-operator-evidence-checklist.md`](audits/quota-reserve-release-operator-evidence-checklist.md).

## WS2 And Durable Runtime

Current async/background behavior remains process-local or route/script-specific. `AnalysisTaskQueue` futures and analysis-task SSE are process-local; durable rows, progress polling, and synthetic worker prototypes are evidence foundations, not production multi-instance recovery.

Public multi-instance deployment remains NO-GO until API A/B route switching, worker lease/retry/failure handling, owner isolation, durable polling replay, SSE limitation handling, and sanitized operator evidence are accepted.

Do not add Redis, Celery, RQ, Kafka, broker dependencies, worker cutovers, migrations, provider/LLM calls, or runtime queue behavior from docs/generator work.

Source provenance: [`docs/operations/background-job-queue-boundary.md`](operations/background-job-queue-boundary.md), [`docs/operations/queue-ws2-metrics-production-readiness.md`](operations/queue-ws2-metrics-production-readiness.md), [`docs/audits/ws2-multi-instance-smoke-test-design.md`](audits/ws2-multi-instance-smoke-test-design.md), [`docs/audits/ws2-multi-user-runtime-cost-control-design.md`](audits/ws2-multi-user-runtime-cost-control-design.md).

## Options And Data Pipeline

Options Lab is an ExperimentConsole, not an execution surface. Current providers are fixture/dry-run contracts; live provider stubs are disabled by default and must fail closed. Do not add broker/order paths, portfolio mutation, live provider calls, global market-provider fallback changes, or tradeable-data claims without explicit safety review.

Data Pipeline R2 treats optional news, sentiment, and detailed fundamentals as progressive enrichment metadata. Optional enrichment gaps must be sanitized and non-blocking; late async merge is future work and should update only bounded metadata unless a separate reviewed recalculation path exists.

Missing provider values must stay missing. Do not fabricate Greeks, IV, bid/ask, volume, open interest, fundamentals, or freshness to make data appear decision-grade.

Source provenance: [`docs/options/README.md`](options/README.md), [`docs/audits/options-provider-adapter-contract.md`](audits/options-provider-adapter-contract.md), [`docs/audits/data-pipeline-r2-progressive-enrichment.md`](audits/data-pipeline-r2-progressive-enrichment.md), [`docs/audits/data-quality-user-disclosure-policy.md`](audits/data-quality-user-disclosure-policy.md), [`docs/audits/trading-no-advice-product-policy.md`](audits/trading-no-advice-product-policy.md).

## Frontend IA And UI Conventions

WolfyStock frontend follows a Reflect-Linear / Linear OS product language: calm, precise, data-rich, route-first, and workbench-oriented. Prefer rows, tables, strips, rails, drawers, and disclosures before card-first dashboards.

Each major route should reveal its primary task in the first viewport. User routes keep raw provider/cache/schema/debug terms collapsed by default; admin/ops pages may be denser but still start with operator state, impact, recommended action, evidence, then details.

New user-facing material should prefer `apps/dsa-web/src/components/linear/`. Existing `Terminal*` names are compatibility adapters, not permission to create a parallel terminal UI system.

Source provenance: [`docs/frontend/README.md`](frontend/README.md), [`docs/frontend/visual-system.md`](frontend/visual-system.md), [`docs/frontend/validation-playbook.md`](frontend/validation-playbook.md), [`docs/frontend/WOLFYSTOCK_FRONTEND_NOISE_BUDGET.md`](frontend/WOLFYSTOCK_FRONTEND_NOISE_BUDGET.md), [`docs/frontend/WOLFYSTOCK_CONSUMER_DATA_QUALITY_UX.md`](frontend/WOLFYSTOCK_CONSUMER_DATA_QUALITY_UX.md), [`docs/frontend/WOLFYSTOCK_ADMIN_MAINTENANCE_OS.md`](frontend/WOLFYSTOCK_ADMIN_MAINTENANCE_OS.md).

## Validation Profiles And Task Workflow

Pick the smallest validation set that proves the current change. Docs/generator tasks use docs/generator commands and secret scan; frontend source changes need route-aware tests and browser evidence; backend/API/auth/provider changes need focused tests and wider gates when protected or shared contracts are near scope.

Standard task modes are `CODEX-ISOLATED`, `SERIAL-MAIN`, `WORKTREE-WORKER`, and `READ-ONLY-AUDIT`. In worktree worker mode, stay in the prompt workspace and branch. Push only when the prompt authorizes it and only to the prompt-named branch.

Never claim completion, readiness, mergeability, or passing status without fresh command evidence. If validation cannot run, report the exact command and blocker.

Source provenance: [`AGENTS.md`](../AGENTS.md), [`docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md`](codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md), [`docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md`](codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md), [`docs/codex/WOLFYSTOCK_CODEX_VALIDATION_MATRIX.md`](codex/WOLFYSTOCK_CODEX_VALIDATION_MATRIX.md), [`docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md`](codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md), [`docs/frontend/validation-playbook.md`](frontend/validation-playbook.md).

## Public Launch NO-GO Blockers

Current public launch status is NO-GO. Existing foundations and offline validators are useful review plumbing, but they do not approve launch and do not replace target-environment operator evidence.

Main blocker families are security/MFA/RBAC, provider/options/data quality, portfolio/backtest safety, WS2 multi-instance runtime, cost/quota/provider circuit enforcement, deployment/backup/rollback, and final release-candidate gates.

Machine-readable launch evidence and operator bundles must remain sanitized and manual-review-only. `releaseApproved=false` remains the safe default unless every hard blocker has accepted external/manual evidence.

Source provenance: [`docs/audits/README.md`](audits/README.md), [`docs/audits/public-launch-readiness-master.md`](audits/public-launch-readiness-master.md), [`docs/audits/public-launch-gap-register.md`](audits/public-launch-gap-register.md), [`docs/audits/deployment-readiness-checklist.md`](audits/deployment-readiness-checklist.md), [`docs/audits/launch-acceptance-evidence-pack.md`](audits/launch-acceptance-evidence-pack.md).

## Known Experimental And Demo-Only Surfaces

Treat fixture-only, demo-only, dry-run, no-send, local-only, diagnostic-only, disabled-by-default, synthetic, fallback, cache-only, and advisory-only labels as hard safety signals.

Current examples include Options fixture/dry-run providers, disabled live options stubs, DuckDB diagnostic/local-only posture, WS2 synthetic worker and process-local SSE limitations, provider source-confidence helpers, optional enrichment metadata, and alert/notification dry-run surfaces.

Do not present these as production-grade, launch-approved, live, billing-authoritative, decision-grade, or tradeable capabilities without separate approval and current validation.

Source provenance: [`docs/audits/options-provider-adapter-contract.md`](audits/options-provider-adapter-contract.md), [`docs/quant-duckdb-engine.md`](quant-duckdb-engine.md), [`docs/alerts/README.md`](alerts/README.md), [`docs/operations/background-job-queue-boundary.md`](operations/background-job-queue-boundary.md), [`docs/operations/queue-ws2-metrics-production-readiness.md`](operations/queue-ws2-metrics-production-readiness.md), [`docs/data-reliability/provider-source-confidence-contract.md`](data-reliability/provider-source-confidence-contract.md), [`docs/audits/data-pipeline-r2-progressive-enrichment.md`](audits/data-pipeline-r2-progressive-enrichment.md).

## Source Inclusion And Exclusion Policy

The generator discovers Markdown files but only includes curated high-signal sources in the manual. This prevents the manual from exceeding practical AI context size and avoids treating old evidence as current truth.

Default inclusions are current authority docs, domain entry points, launch/blocker indexes, Codex workflow docs, and a few targeted domain contracts. Default exclusions are archive lanes, local/generated evidence, task audit dumps, language duplicates, fixture-local READMEs, AI-governance mirrors, and broad legacy guides unless a current source explicitly promotes them.

When source docs conflict, prefer the current prompt, `AGENTS.md`, current code/tests/scripts, and active authority docs. Use archives for provenance only.

Source provenance: [`docs/DOCS_INDEX.md`](DOCS_INDEX.md), [`docs/architecture/file-governance-taxonomy.md`](architecture/file-governance-taxonomy.md), [`docs/ARCHIVE_INDEX.md`](ARCHIVE_INDEX.md), [`docs/audits/README.md`](audits/README.md).

## Source Map

This map is generated from the curated source allowlist. It is a lookup aid, not a replacement for reading the linked sources before editing a domain.

| Manual section | Primary sources | Update trigger | Validation |
| --- | --- | --- | --- |
| Start Here: Authority And Operating Posture | `AGENTS.md`<br>`docs/DOCS_INDEX.md`<br>`docs/WOLFYSTOCK_AI_MAINTENANCE_MANUAL.md`<br>`docs/architecture/file-governance-taxonomy.md` | AI governance, source authority, archive policy, or generated-artifact policy changes. | Docs/generator validation plus `python scripts/check_ai_assets.py` when AI governance assets change. |
| Product Purpose And Current Deployment Boundary | `README.md`<br>`docs/WOLFYSTOCK_SYSTEM_HANDBOOK.md`<br>`docs/DEPLOY.md`<br>`docs/audits/private-beta-readiness.md`<br>`docs/audits/public-launch-readiness-master.md`<br>`docs/audits/trading-no-advice-product-policy.md` | Product positioning, deployment mode, private beta, no-advice, or launch verdict changes. | Docs-only validation for docs changes; release/UAT evidence for deployment posture changes. |
| Architecture And Major Surfaces | `docs/WOLFYSTOCK_SYSTEM_HANDBOOK.md`<br>`docs/architecture/WOLFYSTOCK_MODULE_ARCHITECTURE.md`<br>`docs/architecture/backend-frontend-modular-maintenance-handbook.md`<br>`README.md` | Route map, API group, module ownership, dependency direction, or first-files debug flow changes. | Focused validation for touched surface; architecture docs-only validation for handbook-only changes. |
| Auth, RBAC, And MFA | `docs/audits/index-security-rbac-mfa.md`<br>`docs/audits/auth-rbac-release-security-guide.md`<br>`docs/audits/admin-rbac-r5-coarse-fallback-removal-plan.md`<br>`docs/audits/security-mfa-secret-storage-hardening-plan.md`<br>`docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md` | Any auth, session, capability, MFA, security evidence, admin route, or role-governance change. | Focused auth/RBAC tests, route-capability inventory, redaction checks, and wider gates when enforcement changes. |
| Portfolio And Backtest | `docs/portfolio/README.md`<br>`docs/backtest/README.md`<br>`docs/backtest-system.md`<br>`docs/audits/backtest-portfolio-public-safety-audit.md`<br>`docs/codex/WOLFYSTOCK_BACKTEST_UNIVERSE_RULES.md` | Portfolio accounting/read models, backtest execution/readback/export, public-safety, or owner-isolation changes. | Portfolio/backtest focused tests, golden fixtures, mutation guards, no-advice checks, and owner-isolation evidence when applicable. |
| Provider, Quota, And Cost | `docs/provider-data/README.md`<br>`docs/codex/WOLFYSTOCK_PROVIDER_BUDGET_AND_ROUTING_RULES.md`<br>`docs/audits/index-provider-data-options.md`<br>`docs/audits/index-cost-quota-observability.md`<br>`docs/audits/quota-reserve-release-operator-evidence-checklist.md` | Provider routing/fallback/freshness/cache, quota, circuit, budget, cost, or provider diagnostics changes. | Provider/cache/freshness tests, quota lifecycle tests, no-live-call proof when scoped, and redaction checks. |
| WS2 And Durable Runtime | `docs/operations/background-job-queue-boundary.md`<br>`docs/operations/queue-ws2-metrics-production-readiness.md`<br>`docs/audits/ws2-multi-instance-smoke-test-design.md`<br>`docs/audits/ws2-multi-user-runtime-cost-control-design.md` | Analysis task queue, SSE, durable polling, worker, broker, multi-instance, or WS2 readiness changes. | Synthetic/local smoke first; staging/API A-B evidence and operator artifacts only when deployment posture changes. |
| Options And Data Pipeline | `docs/options/README.md`<br>`docs/audits/options-provider-adapter-contract.md`<br>`docs/audits/data-pipeline-r2-progressive-enrichment.md`<br>`docs/audits/data-quality-user-disclosure-policy.md`<br>`docs/audits/trading-no-advice-product-policy.md` | Options providers, chain/Greeks, scenario copy, optional enrichment, data-quality, or no-advice changes. | Options/data-quality focused tests, fixture/mocked-provider tests, no-order scans, and redaction checks. |
| Frontend IA And UI Conventions | `docs/frontend/README.md`<br>`docs/frontend/visual-system.md`<br>`docs/frontend/validation-playbook.md`<br>`docs/frontend/WOLFYSTOCK_FRONTEND_NOISE_BUDGET.md`<br>`docs/frontend/WOLFYSTOCK_CONSUMER_DATA_QUALITY_UX.md`<br>`docs/frontend/WOLFYSTOCK_ADMIN_MAINTENANCE_OS.md` | Frontend route taxonomy, primitives, route IA, visual system, consumer/admin disclosure, or browser-evidence rules change. | Frontend focused tests plus lint/build/browser evidence when UI source or visual behavior changes. |
| Validation Profiles And Task Workflow | `AGENTS.md`<br>`docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md`<br>`docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md`<br>`docs/codex/WOLFYSTOCK_CODEX_VALIDATION_MATRIX.md`<br>`docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md`<br>`docs/frontend/validation-playbook.md` | Task modes, prompt fields, validation matrix, final report format, or frontend evidence rules change. | Run the task-required commands; docs-only changes use diff-check/status/secret scan unless task says otherwise. |
| Public Launch NO-GO Blockers | `docs/audits/README.md`<br>`docs/audits/public-launch-readiness-master.md`<br>`docs/audits/public-launch-gap-register.md`<br>`docs/audits/deployment-readiness-checklist.md`<br>`docs/audits/launch-acceptance-evidence-pack.md` | Launch verdict, blocker register, release checklist, operator evidence contract, or launch acceptance process changes. | Docs-only validation for launch docs; release-grade gates and sanitized operator evidence for actual launch posture changes. |
| Known Experimental And Demo-Only Surfaces | `docs/audits/options-provider-adapter-contract.md`<br>`docs/quant-duckdb-engine.md`<br>`docs/alerts/README.md`<br>`docs/operations/background-job-queue-boundary.md`<br>`docs/operations/queue-ws2-metrics-production-readiness.md`<br>`docs/data-reliability/provider-source-confidence-contract.md`<br>`docs/audits/data-pipeline-r2-progressive-enrichment.md` | Any diagnostic/demo/fixture/dry-run surface becomes runtime, production, or user-visible decision authority. | Fail-closed tests, no-live-call proof, redaction checks, docs wording review, and task-specific runtime evidence. |
| Source Inclusion And Exclusion Policy | `docs/DOCS_INDEX.md`<br>`docs/architecture/file-governance-taxonomy.md`<br>`docs/ARCHIVE_INDEX.md`<br>`docs/audits/README.md` | Docs taxonomy, archive policy, generated artifact policy, or manual source curation changes. | Run this generator twice and prove deterministic output; run docs diff-check and secret scan. |

## JSON Manifest

The machine-readable manifest is generated at `docs/AI_PROJECT_MANUAL_SOURCES.json`. It records source paths, titles, purposes, categories, SHA-256 hashes, byte counts, line counts, manual sections, and discovery/exclusion statistics.

Current discovery summary:

- Markdown discovered after pruned directory rules: 356
- Candidate Markdown after exclusion policy: 213
- Curated sources included in this manual: 53

Exclusion policy:

- `.git/**`
- `node_modules/**`
- `dist/**`
- `static/**`
- `coverage/**`
- `reports/** unless explicitly high-value`
- `worktree_archives/**`
- `archive folders unless explicitly allowlisted`
- `docs/codex/audits/** task reports unless explicitly promoted by a current source`
- `local/generated evidence such as .codex/**, .claude/reviews/**, artifacts/**, screenshots/**, and test-results/**`
- `AI-governance mirrors such as CLAUDE.md and .github/copilot-instructions.md when AGENTS.md is available`
- `language duplicates and broad translated guides unless generating a language-specific manual`
