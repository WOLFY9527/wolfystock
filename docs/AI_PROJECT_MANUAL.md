# WolfyStock AI Project Manual

> GENERATED FILE. DO NOT EDIT DIRECTLY.
>
> Edit `scripts/build_ai_project_manual.py` or the tiny canonical source files, then run `python scripts/build_ai_project_manual.py`.
> Check freshness with `python scripts/build_ai_project_manual.py --check`.

Status: generated comprehensive project handbook after the DOCS-006 hard Markdown collapse.
Audience: future AI models, Codex workers, review agents, maintainers, and humans assigning AI work.
Authority: operational handbook and source map; `AGENTS.md` remains the repository AI-collaboration rule source.
Do not use as: launch approval, protected-domain authorization, stale audit authority, trading advice, or replacement for current source/test inspection.

## Table Of Contents

- [Project Identity And Product Purpose](#project-identity-and-product-purpose)
- [Architecture Overview](#architecture-overview)
- [Frontend Surfaces](#frontend-surfaces)
- [Backend API And Service Structure](#backend-api-and-service-structure)
- [Data Providers And Data Reality Boundaries](#data-providers-and-data-reality-boundaries)
- [Market, Options, Macro, Liquidity, Backtest, Scenario, And Portfolio Domains](#market-options-macro-liquidity-backtest-scenario-and-portfolio-domains)
- [Professional Analytics Roadmap And Readiness](#professional-analytics-roadmap-and-readiness)
- [Protected Domains And Safety Rules](#protected-domains-and-safety-rules)
- [No-Advice Policy](#no-advice-policy)
- [Validation Matrix](#validation-matrix)
- [Codex Workflow And Landing Changes](#codex-workflow-and-landing-changes)
- [Current Canonical File Map](#current-canonical-file-map)
- [Compressed Project History](#compressed-project-history)
- [AI Onboarding Checklist](#ai-onboarding-checklist)
- [Source Map](#source-map)
- [JSON Manifest](#json-manifest)

## Project Identity And Product Purpose

WolfyStock is a professional financial research terminal for market operators, discretionary research, and portfolio workflows across US, CN, and HK markets. It combines market context, scanner discovery, watchlists, rule backtesting, portfolio tracking, provider diagnostics, admin observability, and AI-assisted research in a Python/FastAPI plus React/TypeScript codebase.

The product solves the problem of fragmented research evidence: market regime, quote/history readiness, portfolio exposure, scenario shocks, options context, and backtest evidence are easy to confuse when they come from different providers and freshness levels. WolfyStock's durable direction is to show the evidence, source authority, lineage, and readiness boundary before any research conclusion.

It is not a broker, order-entry surface, retail trading game, or unconstrained LLM wrapper. All user-visible research must stay analytical and no-advice.

Source provenance: [`README.md`](../README.md), [`AGENTS.md`](../AGENTS.md).

## Architecture Overview

Main runtime entrypoints are `main.py` for analysis/local automation, `server.py` and `api/app.py` for the FastAPI app, `api/v1/router.py` for API grouping, `src/services/` for business services, `src/repositories/` for persistence boundaries, `src/schemas/` for DTO/schema contracts, `data_provider/` for provider adapters and fallback normalization, `bot/` for notification integrations, `apps/dsa-web/` for the web terminal, `apps/dsa-desktop/` for the Electron wrapper, `scripts/` for local and CI utilities, and `.github/workflows/` for CI/release automation.

Maintain bounded contexts. Consumers should call public facades, API clients, schemas, DTOs, validators, and documented commands. Do not reach into private engines, repositories, provider clients, cache keys, ledger internals, or mutation code from another domain just to make a local task easier.

Shared contracts, schema changes, root config, CI, dependency files, auth, provider runtime, broker/accounting, DB migrations, and frontend route-entry behavior are high-risk and require explicit task scope.

Source provenance: [`AGENTS.md`](../AGENTS.md), [`README.md`](../README.md).

## Frontend Surfaces

| Surface | Purpose | Primary ownership | Readiness boundary |
| --- | --- | --- | --- |
| Market Overview | Regime, breadth, official risk, and macro first read | `api/v1/endpoints/market_overview.py`, `src/services/market_overview_service.py`, `apps/dsa-web/src/pages/MarketOverviewPage.tsx` | Partial until official risk, quote authority, and target-environment evidence are proven. |
| Scanner | Candidate discovery and watchlist handoff | `api/v1/endpoints/scanner.py`, `src/services/market_scanner_service.py`, `apps/dsa-web/src/pages/UserScannerPage.tsx` | Partial; quote, history, universe, freshness, turnover, and packet readiness must fail closed. |
| Watchlist | Saved symbols and row-level research queue | `api/v1/endpoints/watchlist.py`, `src/services/watchlist_service.py`, `src/services/watchlist_research_overlay_service.py`, `apps/dsa-web/src/pages/WatchlistPage.tsx` | Partial; row packets may lack quote freshness, catalyst age, or scanner lineage and must say so. |
| Stock Detail | Symbol research packet and structure decision | `api/v1/endpoints/stocks.py`, `src/services/stock_service.py`, `src/services/stock_structure_decision_service.py` | Partial; no invented quote, fundamental, event, SEC, peer, or catalyst evidence. |
| Liquidity Monitor | Capital pressure and stress context | `api/v1/endpoints/liquidity_monitor.py`, `src/services/liquidity_monitor_service.py`, `apps/dsa-web/src/pages/LiquidityMonitorPage.tsx` | Partial; macro, flow, and proxy rows remain capped unless official source authority exists. |
| Rotation Radar | ETF/index family rotation context | `api/v1/endpoints/market.py`, rotation services, `apps/dsa-web/src/pages/MarketRotationRadarPage.tsx` | Partial; quote coverage, membership, and official source authority gate headline claims. |
| Options Lab | Read-only options research console | `api/v1/endpoints/options.py`, `src/services/options_lab_service.py`, `apps/dsa-web/src/pages/OptionsLabPage.tsx` | Observation-only unless entitlement, redisplay, chain, Greeks, IV, OI, volume, and methodology proof exist. |
| Scenario Lab | Bounded shock comparison | `api/v1/endpoints/market.py`, `src/services/market_scenario_lab_engine.py`, `apps/dsa-web/src/pages/ScenarioLabPage.tsx` | Partial; sample, request-supplied, fallback, or static baselines are observation-only. |
| Backtest | Deterministic rule backtest and stored readback | `api/v1/endpoints/backtest.py`, `src/core/rule_backtest_engine.py`, `src/services/backtest_service.py`, `apps/dsa-web/src/pages/BacktestPage.tsx` | Research-useful v1 semantics; no optimizer, winner, allocation, or fake performance semantics. |
| Portfolio | Accounts, holdings, cash, FX, ledger, risk, and attribution | `api/v1/endpoints/portfolio.py`, `src/services/portfolio_service.py`, `apps/dsa-web/src/pages/PortfolioPage.tsx` | Accounting authority is protected; price/FX lineage and broker/order implications must stay explicit. |
| Admin/Ops | Operator observability and protected diagnostics | `api/v1/endpoints/admin/*`, `src/services/admin_*`, `apps/dsa-web/src/pages/Admin*` | Manual-review-gated; never leak raw provider, credential, security, or internal payload details. |

Frontend work should preserve the operator-terminal posture: dense but legible, route-first, evidence-first, and calm. Prefer tables, rows, rails, drawers, strips, and explicit disclosure states over generic card sprawl. Each route should make the primary research task visible in the first viewport and should keep raw provider, cache, schema, debug, credential, and fallback internals out of consumer copy.

Source provenance: [`README.md`](../README.md), [`AGENTS.md`](../AGENTS.md).

## Backend API And Service Structure

Backend/API work should keep API routers thin, services authoritative for business semantics, repositories responsible for persistence, schemas/DTOs explicit, and provider adapters isolated behind provider-runtime boundaries. FastAPI endpoints should not embed scanner ranking math, portfolio accounting, provider fallback ordering, auth policy, or report rendering internals.

Core API families include auth, analysis, history, stocks, scanner, watchlist, market overview, market/scenario, liquidity, rotation, options, portfolio, backtest, quant, system, usage, admin, and diagnostics. Additive fields are preferred over breaking response contracts; deleted or renamed fields require client compatibility review.

For Python changes, prefer `./scripts/ci_gate.sh`. At minimum run `python -m py_compile <changed_python_files>` and the closest deterministic tests. Protected semantic changes need focused regression evidence.

Source provenance: [`AGENTS.md`](../AGENTS.md), [`README.md`](../README.md).

## Data Providers And Data Reality Boundaries

Provider runtime owns provider order, fallback, retry/circuit behavior, timeout posture, freshness labels, source authority, display rights, optional enrichment budgets, sanitized diagnostics, and cache/local-first behavior. Do not reorder providers, deepen live fallback, add broad optional fanout, or expose raw provider payloads without explicit scope.

Fallback, cached, proxy, repaired, inferred, fixture, synthetic, dry-run, parser-only, request-supplied, and observation-only data must remain visibly not-live and not-decision-grade. Missing data stays missing; do not fabricate quote, fundamental, event, IV, Greek, bid/ask, OI, volume, FX, benchmark, or source-freshness fields.

| Data family | Readiness | Operational boundary |
| --- | --- | --- |
| Official risk and volatility | Partial | VIX/volatility, rates, Fed liquidity, credit stress, and official macro rows must be source-authorized before score-grade claims. |
| Authorized quote spine | Partial | US/CN/HK quote and daily OHLCV snapshots need durable lineage, freshness, and redisplay/display authority. |
| Index/ETF membership | Partial | Rotation and market claims need official membership and weighting proof, not proxy-only membership. |
| Scanner universe/history | Partial | Universe, local history, quote freshness, turnover, and evidence packets must gate scanner summaries. |
| Fundamentals/filings/events | Partial | Ratios, filings, catalysts, events, and peers are fragmented; missing values remain missing. |
| Options chains/Greeks | Blocked or observation-only | No production-grade claims without provider entitlement, redisplay rights, methodology proof, and chain/Greek completeness. |
| Scenario baselines | Partial | Durable baseline snapshots and target-environment evidence are required before scenario state can be authoritative. |
| Backtest lineage | Partial but research-useful | Adjusted basis, calendar, point-in-time universe, reproducibility, and stored-result authority gate professional claims. |
| Factor research lineage | Diagnostic-only | No PIT universe or long-short factor-return contract yet; do not promote factor helpers as ranking truth. |
| Portfolio price/FX lineage | Partial | Valuation is only as credible as quote, FX, timestamp, source, and account/ledger provenance. |

Source provenance: [`AGENTS.md`](../AGENTS.md), [`README.md`](../README.md).

## Market, Options, Macro, Liquidity, Backtest, Scenario, And Portfolio Domains

Market Overview, Liquidity, and Rotation depend on official risk, macro, ETF/index quote coverage, and membership authority. They may show bounded context, but they must not convert proxy breadth or quote-derived approximations into score-grade institutional claims.

Options Lab is a read-only experiment console. It is not an execution surface, strategy-ranking engine, or order workflow. Fixture/dry-run providers and disabled live stubs must fail closed until entitlement, redisplay rights, chain completeness, Greeks/IV/OI/volume methodology, and display authority are proven.

Scenario Lab compares bounded shocks. Request-supplied, fallback, static, sample, or stale baselines are observation-only and must not imply execution readiness.

Backtest owns deterministic rule evaluation, stored result readback, exports, compare workflows, and research-useful v1 semantics. Do not change fills, costs, metrics, benchmark semantics, parameter/winner meaning, local-only universe execution, or stored-result authority without explicit versioning and focused tests.

Portfolio owns accounts, holdings, cash, transactions, P&L, FX/native currency, cost basis, broker sync/import overlays, ledger mutations, and read projections. UI work must not recalculate accounting authority or imply broker order execution.

Source provenance: [`AGENTS.md`](../AGENTS.md), [`README.md`](../README.md).

## Professional Analytics Roadmap And Readiness

The professional roadmap is not a promise that a family is live. It is an ordered readiness map:

1. Official VIX/volatility and macro/rates/Fed-liquidity source authority.
2. Authorized US/CN/HK quote spine with lineage, freshness, and display rights.
3. US index/ETF quote coverage and official membership/weight proofs.
4. Scanner universe, history, turnover, and quote-readiness gates.
5. Watchlist row packet and single-stock research packet completeness.
6. Portfolio price and FX lineage.
7. Options provider entitlement, redisplay rights, and methodology proof.
8. Scenario durable baseline snapshots and target-environment evidence.
9. Backtest dataset lineage, adjusted basis, calendar, PIT universe, and reproducibility gates.
10. Factor research lineage with PIT membership and return contracts.

Each step must expose blocked, partial, missing, unauthorized, stale, or observation-only states rather than hiding them behind positive copy.

Source provenance: [`README.md`](../README.md), [`AGENTS.md`](../AGENTS.md).

## Protected Domains And Safety Rules

Stop before editing these domains unless the prompt explicitly authorizes the scope and validation path:

- provider adapters, provider order, fallback, freshness, cache semantics, live-call behavior, credentials, and source authority;
- scanner scoring, selection, thresholds, ranking, sorting, score contribution, and live/fallback labels;
- backtest fills, costs, metrics, benchmarks, parameter/winner semantics, universe execution, and stored readback;
- portfolio accounting, cash, holdings, transactions, P&L, FX/native currency, cost basis, broker sync/import, and ledger semantics;
- auth/RBAC/security, sessions, cookies, CSRF/CORS, password/token handling, MFA, and admin protection;
- DB migrations, root config, package/lock files, CI, dependency updates, env templates, and external network behavior;
- broker/order execution, trading CTAs, target prices, position sizing, and personalized financial advice.

Do not introduce fake data, fallback payloads, placeholder readiness, hidden compatibility layers, raw provider leakage, or one-off Markdown reports as a way to satisfy a task.

Source provenance: [`AGENTS.md`](../AGENTS.md).

## No-Advice Policy

WolfyStock may provide research context, evidence, readiness state, scenario comparison, risk disclosure, and operational diagnostics. It must not provide direct instructions to buy, sell, hold, short, add, reduce, execute, route, or size positions for a user.

Avoid user-facing copy that implies investment recommendation, guaranteed outcome, target price, execution readiness, risk-free action, or personalized suitability. Safer patterns are observation-only labels, evidence boundaries, uncertainty, data-source/freshness/lineage, and explicit no-advice wording. The Chinese no-advice anchor `数据不足，暂不形成结论。` is intentionally retained where product copy needs a compact blocked-state sentence.

No-advice review should classify grep hits. Tests, negative assertions, source-code identifiers, and policy docs may contain forbidden words as guardrails; visible UI and generated reports need stricter review.

Source provenance: [`AGENTS.md`](../AGENTS.md).

## Validation Matrix

Use the smallest validation set that proves the touched behavior:

- Docs/manual/generator: `python -m py_compile scripts/build_ai_project_manual.py`, `python scripts/build_ai_project_manual.py`, `python scripts/build_ai_project_manual.py --check`, `python -m pytest -q tests/scripts/test_build_ai_project_manual.py`, `python scripts/check_ai_assets.py`, `git diff --check`, `bash scripts/release_secret_scan.sh --base-ref origin/main`, inventory counts, and link sanity.
- Backend Python: `./scripts/ci_gate.sh` when feasible; otherwise `python -m py_compile <changed_python_files>` plus closest deterministic pytest.
- API/schema/auth/provider/protected contracts: backend focused tests, compatibility review, redaction/leakage checks, and wider gates when shared contracts are touched.
- Web frontend: from `apps/dsa-web`, run dependency install only when needed, then `npm run lint`, `npm run build`, and concrete Vitest paths. Use browser/screenshot smoke when layout or visible UX changes.
- Local UAT runtime harness: `python scripts/uat_runtime_harness.py --expected-sha "$(git rev-parse HEAD)"`, then use `python scripts/uat_runtime_harness.py --preflight --expected-sha "$(git rev-parse HEAD)" --evidence-path <run-evidence> --json` for read-only WorkBuddy qualification and `--stop-from-evidence --evidence-path <run-evidence> --json` for task-owned cleanup.

> Shell note: commands using `./scripts/*.sh` and `$(git rev-parse HEAD)` are
> POSIX-shell (bash/sh) syntax. On Windows run them from Git Bash, WSL, or any
> shell providing a POSIX `sh` (e.g. `bash scripts/ci_gate.sh`). PowerShell uses
> the same `$(...)` subexpression syntax, so the UAT `--expected-sha "$(git rev-parse HEAD)"`
> invocations also work unchanged in PowerShell.
- Desktop: build web first, then desktop build where platform allows.
- Workflow/scripts/Docker: run the closest local deterministic script or syntax check and report unexecuted remote/infra gaps.

Never claim tests passed unless the command actually ran in this workspace and succeeded.

Source provenance: [`AGENTS.md`](../AGENTS.md), [`README.md`](../README.md).

## Codex Workflow And Landing Changes

Start with read-only discovery. Confirm `pwd`, branch, and `git status`; read the current prompt, `AGENTS.md`, `README.md`, this manual, and the smallest code/docs context required. Respect task mode and workspace. In a `WORKTREE-WORKER` task, stay inside the specified worktree and branch.

Do not push unless explicitly authorized. Do not commit unless the task asks for a commit or the current instruction grants auto-commit. Do not rebase, merge, delete branches/worktrees, or rewrite history unless the task explicitly requires it. If a task requires fetch/rebase before final report, run `git fetch origin`, rebase onto `origin/main`, rerun focused validation, and only then commit/report.

Before final delivery: inspect `git diff`, run `git diff --check`, run required tests/checks, confirm no unexpected files or secrets, and report exact commands and results. Final reports should include status, changed files, validation, risk, final base commit, commit hash when created, final `git status`, and rollback command.

Source provenance: [`AGENTS.md`](../AGENTS.md), [`docs/DOCS_INDEX.md`](DOCS_INDEX.md).

## Current Canonical File Map

After DOCS-006, the repository intentionally avoids a large Markdown corpus. The canonical reading path should be:

1. `README.md` for the human product entrypoint and run commands.
2. `AGENTS.md` for current AI-agent rules and hard safety boundaries.
3. `docs/AI_PROJECT_MANUAL.md` for the comprehensive project handbook.

Retained Markdown categories:

| File or lane | Why retained |
| --- | --- |
| `README.md` | Short human entrypoint and run-command starter. |
| `AGENTS.md` | Repository AI-collaboration source of truth and protected-domain hard rules. |
| `CLAUDE.md` | Required symlink to `AGENTS.md` for Claude compatibility; retained because `scripts/check_ai_assets.py` enforces it. |
| `docs/AI_PROJECT_MANUAL.md` | Generated comprehensive handbook for AI workers and maintainers. |
| `docs/DOCS_INDEX.md` | Tiny pointer to canonical docs; no archive lane or broad index. |
| `docs/CHANGELOG.md` | Short compatibility file retained because release tooling still reads this path. |
| `.github/*.md` | GitHub Copilot/instruction/issue/PR workflow assets. |
| `.claude/skills/*.md` | Required repository skill assets checked by AI governance tooling. |

`docs/AI_PROJECT_MANUAL_SOURCES.json` is not Markdown; it records deterministic source hashes, generator metadata, discovery counts, and section provenance. `docs/DOCS_INDEX.md` should stay tiny and only point to canonical files. Archive and product-recovery Markdown lanes are no longer retained as active project knowledge.

Source provenance: [`README.md`](../README.md), [`AGENTS.md`](../AGENTS.md), [`docs/DOCS_INDEX.md`](DOCS_INDEX.md).

## Compressed Project History

WolfyStock began as a scheduled stock-analysis and notification project, then accumulated web, desktop, provider, backtest, portfolio, admin, and AI-assisted research surfaces. Later work shifted the architecture toward bounded contexts, provider/source readiness, route-level research workbenches, and protected semantics around scanner, portfolio, backtest, auth/RBAC, broker/accounting, and provider runtime.

Product-recovery and DATA-series work established the durable lesson that visible research value depends on real source authority: official risk/macro, authorized quote spine, scanner/watchlist packets, portfolio price/FX lineage, options entitlement, scenario baselines, and backtest dataset lineage must be explicit. Old audits, acceptance reports, launch checklists, design notes, and progress logs were useful for their moment, but their durable content now lives in this manual.

DOCS-006 hard-collapsed the Markdown corpus: keep a short README, a short AGENTS rule entrypoint, this generated manual, the manifest, and required governance/workflow mirrors. Do not recreate old index/archive lanes for routine tasks.

Source provenance: [`README.md`](../README.md), [`docs/DOCS_INDEX.md`](DOCS_INDEX.md).

## AI Onboarding Checklist

For a new task:

1. Confirm CWD, branch, and `git status --short --branch`.
2. Read the user's task contract and protected/forbidden scope.
3. Read `AGENTS.md`, `README.md`, and this manual.
4. Run read-only discovery with `rg`, `rg --files`, source files, tests, and scripts. Do not edit during discovery.
5. Classify the task as docs, backend, frontend, API/schema, provider, auth, portfolio, backtest, workflow, or review.
6. If the task touches a protected domain, stop unless explicit scope and validation are present.
7. Make the smallest relevant change; avoid new docs, indexes, archive lanes, or parallel implementations.
8. Run the focused validation that proves the touched area.
9. Inspect diff/status, secret scan when required, and link/Markdown sanity for docs work.
10. If the prompt requires rebase, fetch/rebase and rerun focused validation before final report or commit.

For docs tasks, the default answer is to update this manual/generator and delete stale Markdown after durable knowledge is absorbed.

Source provenance: [`AGENTS.md`](../AGENTS.md), [`README.md`](../README.md), [`docs/DOCS_INDEX.md`](DOCS_INDEX.md).

## Source Map

This map is generated from the hard-collapse source set. The manual contains absorbed durable knowledge from retired docs, but only these canonical files remain source-tracked.

| Manual section | Tracked sources | Update trigger | Validation |
| --- | --- | --- | --- |
| Project Identity And Product Purpose | `README.md`<br>`AGENTS.md` | Product positioning, target audience, or no-advice posture changes. | Docs-only validation plus no-advice grep when user-visible wording changes. |
| Architecture Overview | `AGENTS.md`<br>`README.md` | Runtime entrypoints, module ownership, public contracts, or high-risk boundary rules change. | Run the focused gate for the touched module plus `python scripts/check_ai_assets.py` for AI-governance edits. |
| Frontend Surfaces | `README.md`<br>`AGENTS.md` | Route map, page ownership, consumer copy, route IA, or visual system changes. | Frontend tests/lint/build plus browser or screenshot evidence when UI source changes. |
| Backend API And Service Structure | `AGENTS.md`<br>`README.md` | API families, service boundaries, schema contracts, report payloads, or validation routing changes. | Backend gate or closest pytest/py_compile evidence; wider gates for protected/shared contracts. |
| Data Providers And Data Reality Boundaries | `AGENTS.md`<br>`README.md` | Provider routing, source authority, data readiness, freshness, lineage, or professional-roadmap changes. | Provider/cache/freshness tests, no-live-call proof when relevant, and raw-provider leakage scans. |
| Market, Options, Macro, Liquidity, Backtest, Scenario, And Portfolio Domains | `AGENTS.md`<br>`README.md` | Any domain readiness, public copy, protected math/accounting, options authority, or macro/liquidity source change. | Domain-focused tests plus no-advice and leakage checks; never use unrelated green tests as proof. |
| Professional Analytics Roadmap And Readiness | `README.md`<br>`AGENTS.md` | Professional data roadmap, readiness labels, or evidence-harness expectations change. | Docs/generator validation for handbook changes; domain validation for implementation changes. |
| Protected Domains And Safety Rules | `AGENTS.md` | Any protected boundary or safety policy changes. | Focused tests for the exact protected semantic plus diff/status/secret/no-advice checks before reporting completion. |
| No-Advice Policy | `AGENTS.md` | User-facing research copy, generated reports, product policy, options/backtest/portfolio wording, or no-advice guards change. | Focused grep/classification plus relevant page/report tests. |
| Validation Matrix | `AGENTS.md`<br>`README.md` | Validation commands, CI gates, protected test expectations, or docs/generator workflow changes. | Run the validation relevant to this manual/generator when edited. |
| Codex Workflow And Landing Changes | `AGENTS.md`<br>`docs/DOCS_INDEX.md` | Task modes, git policy, final-report requirements, or AI workflow rules change. | Docs/generator check and `python scripts/check_ai_assets.py` when governance assets change. |
| Current Canonical File Map | `README.md`<br>`AGENTS.md`<br>`docs/DOCS_INDEX.md` | Canonical docs set, retained Markdown policy, or AI asset governance changes. | Inventory before/after counts, link sanity, generator `--check`, and `python scripts/check_ai_assets.py`. |
| Compressed Project History | `README.md`<br>`docs/DOCS_INDEX.md` | Major project direction, docs-retention policy, or historical context changes. | Docs-only validation and inventory count check. |
| AI Onboarding Checklist | `AGENTS.md`<br>`README.md`<br>`docs/DOCS_INDEX.md` | Onboarding order, docs model, or task execution policy changes. | Generator check plus AI asset check. |

## JSON Manifest

The machine-readable manifest is generated at `docs/AI_PROJECT_MANUAL_SOURCES.json`. It records source paths, source hashes, generator metadata, section provenance, and Markdown discovery statistics.

Current discovery summary:

- Markdown discovered after pruned directory rules, excluding this generated manual: 19
- Candidate Markdown after hard-collapse policy: 3
- Curated sources included in this manual: 3

Exclusion policy:

- Keep the manual source set intentionally tiny: AGENTS.md, README.md, and docs/DOCS_INDEX.md.
- Do not rediscover archive lanes, task reports, stale audits, old plans, or one-off acceptance snapshots as manual sources.
- Keep .github and .claude Markdown files as governance/workflow mirrors when required by scripts/check_ai_assets.py, but do not treat them as handbook sources.
- Keep issue and PR templates as GitHub workflow assets, not project handbook chapters.
- Exclude generated outputs, local evidence, fixture READMEs, language duplicates, broad legacy guides, and dependency/build/cache folders.
- When durable knowledge is needed, merge it into this deterministic generator/manual instead of adding another index or archive file.
