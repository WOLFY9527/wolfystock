# WolfyStock System Handbook

This handbook is the human and AI maintenance entry layer for the current
WolfyStock repository. It summarizes system shape, ownership, routes, API
groups, provider/data rules, validation posture, and safe modification paths.

It links to source documents instead of replacing them. If this handbook and an
executable file disagree, inspect the current code and update the docs in the
same task when that is in scope.

## Product Purpose

WolfyStock is a professional financial research terminal. It combines market
overview, scanner discovery, watchlists, rule backtesting, portfolio tracking,
AI-assisted analysis, provider diagnostics, and admin observability.

The product is not a broker, order-entry surface, or generic retail stock app.
It must preserve analytical and no-advice boundaries. Do not add trade/order
affordances, broker execution, buy/sell CTAs, or personalized financial advice
unless a separate safety-reviewed task explicitly scopes that change.

Source docs:

- [README](../README.md)
- [Trading no-advice product policy](./audits/trading-no-advice-product-policy.md)
- [WolfyStock Modular Architecture Manual](./architecture/WOLFYSTOCK_MODULE_ARCHITECTURE.md)

## Operator Workflows

Common operator workflows are:

1. Start from market context: open Market Overview, Liquidity Monitor, or
   Rotation Radar to understand regime, breadth, source state, and degraded
   data posture.
2. Discover candidates: run Scanner for a bounded market profile and review
   ranked candidates, reasons, risks, history, and watchlist handoff.
3. Deepen a symbol: use Home or Chat for analysis and report workflows.
4. Validate a rule: use Backtest, result pages, support exports, and compare
   workbench without changing stored result semantics.
5. Track exposure: use Portfolio for holdings, cash, FX/native currency,
   ledger rows, broker sync/import overlays, and risk views.
6. Experiment safely: use Options Lab as a read-only experiment console with
   fixture/dry-run data boundaries unless live adapters are separately
   approved.
7. Operate the system: use admin logs, provider operations, provider circuits,
   cost observability, notifications, users/security, and system settings for
   diagnostics and controlled admin actions.

## Runtime And Repository Entry Points

| Area | Entry point |
| --- | --- |
| CLI/local analysis | `main.py` |
| FastAPI service | `server.py`, `api/app.py`, `api/v1/router.py` |
| Web terminal | `apps/dsa-web/` |
| Desktop wrapper | `apps/dsa-desktop/` |
| Backend services | `src/services/` |
| Backend repositories | `src/repositories/` |
| Provider adapters | `data_provider/` |
| API endpoints | `api/v1/endpoints/` |
| Bot integrations | `bot/` |
| Local scripts | `scripts/` |
| GitHub automation | `.github/workflows/`, `.github/scripts/` |
| Tests | `tests/`, `apps/dsa-web/src/**/__tests__/`, Playwright specs |

## Current Frontend Route Map

The active web route map is defined in `apps/dsa-web/src/App.tsx`. Routes are
also available with locale prefixes such as `/zh/...` and `/en/...` where the
router defines localized branches.

| Route | Surface class | Primary owner |
| --- | --- | --- |
| `/` | ResearchConsole | Home analysis and report workflow |
| `/guest` | Guest surface | Guest preview and paywall path |
| `/scanner` | RankingBoard | Scanner run/results/watchlist handoff |
| `/chat` | Research/chat surface | Ask-stock and AI conversation workflow |
| `/portfolio` | RiskConsole / LedgerBoard | Portfolio holdings, risk, ledger, sync/import |
| `/market-overview` | MarketMonitor | Market regime and comparative panels |
| `/market/liquidity-monitor` | MarketMonitor | Liquidity diagnostics |
| `/market/rotation-radar` | MarketMonitor | Rotation radar and theme state |
| `/watchlist` | WatchBoard / DenseList | User watchlist workflow |
| `/backtest` | Backtest workbench | Backtest configuration and submission |
| `/backtest/results/:runId` | Backtest result | Stored-first result readback |
| `/backtest/compare` | Compare workbench | Stored-first run comparison |
| `/options-lab` | ExperimentConsole | Options hypothesis and chain/matrix workspace |
| `/settings` | Personal settings | User settings |
| `/settings/system` | OpsConsole | Admin-gated system settings |
| `/admin/logs` | OpsConsole | Execution and audit logs |
| `/admin/evidence-workflow` | OpsConsole | Evidence workflow diagnostics |
| `/admin/notifications` | OpsConsole | Notification route diagnostics/control |
| `/admin/market-providers` | OpsConsole | Provider operations |
| `/admin/provider-circuits` | OpsConsole | Provider circuit diagnostics |
| `/admin/users` | OpsConsole | Admin user governance |
| `/admin/cost-observability` | OpsConsole | Cost and usage observability |
| `/login`, `/reset-password` | Auth pages | Authentication flow |

Route taxonomy authority:

- [Linear OS Design Language](./codex/WOLFYSTOCK_LINEAR_OS_DESIGN_LANGUAGE.md)
- [Frontend Surface Usage](./codex/WOLFYSTOCK_FRONTEND_SURFACE_USAGE.md)
- [Frontend Route Templates](./codex/WOLFYSTOCK_FRONTEND_ROUTE_TEMPLATES.md)
- [Canonical UI Primitives](./design/wolfystock-canonical-ui-primitives.md)

## T-196 Route Migration Status

Treat the Linear OS route migration as partial unless current code, tests, and
browser evidence prove the exact route you are touching.

Current `origin/main` evidence at the time this handbook was created includes
landed commits for:

- T-196C Market Overview to `MarketMonitor`.
- T-196E Options Lab to `ExperimentConsole`.
- Portfolio to `RiskConsole`.

Do not infer that every route is fully migrated from those commits. Before a
task claims completion for a route family, inspect the current page file,
tests, surface docs, and route-level browser proof. For pages not directly
verified in the task, write `pending`, `partial`, or `not inspected`.

## API Group Map

`api/v1/router.py` mounts all v1 API groups under `/api/v1`.

| Prefix | Endpoint module | Responsibility |
| --- | --- | --- |
| `/api/v1/auth` | `api/v1/endpoints/auth.py` | Login, sessions, password/MFA/security flows |
| `/api/v1/agent` | `api/v1/endpoints/agent.py` | Agent status, models, skills, chat |
| `/api/v1/analysis` | `api/v1/endpoints/analysis.py` | Stock analysis, task status, reports |
| `/api/v1/history` | `api/v1/endpoints/history.py` | Analysis history |
| `/api/v1/stocks` | `api/v1/endpoints/stocks.py` | Stock import, image extraction, parsing |
| `/api/v1/backtest` | `api/v1/endpoints/backtest.py` | Standard and rule backtest APIs |
| `/api/v1/scanner` | `api/v1/endpoints/scanner.py` | Scanner run, readback, watchlists |
| `/api/v1/system` | `api/v1/endpoints/system_config.py` | System config and provider tests |
| `/api/v1/usage` | `api/v1/endpoints/usage.py` | Usage summary |
| `/api/v1/portfolio` | `api/v1/endpoints/portfolio.py` | Portfolio accounts, holdings, ledger, import/sync |
| `/api/v1/watchlist` | `api/v1/endpoints/watchlist.py` | Watchlist CRUD and actions |
| `/api/v1/market-overview` | `api/v1/endpoints/market_overview.py` | Market overview panels |
| `/api/v1/market` | `api/v1/endpoints/market.py`, `liquidity_monitor.py` | Market snapshots, rotation, liquidity |
| `/api/v1/quant` | `api/v1/endpoints/quant.py` | Optional DuckDB diagnostics |
| `/api/v1/options` | `api/v1/endpoints/options.py` | Options Lab fixture/dry-run APIs |
| `/api/v1/admin/*` | admin endpoint modules | Users, portfolio projections, security, logs, notifications, cost, provider ops, provider circuits |

Health/readiness endpoints such as `/api/health`, `/api/health/live`, and
`/api/health/ready` are outside the `/api/v1` router and are documented in the
full guide and deployment materials.

For endpoint details, prefer current code, Swagger at `/docs`, and these
references:

- [Full Guide API section](./full-guide.md)
- [Backtest System](./backtest-system.md)
- [Market Scanner](./market-scanner.md)
- [DuckDB Operator Smoke Guide](./operations/duckdb-operator-smoke-guide.md)

## Backend Protected Domains

The protected backend domains are semantic boundaries. Do not change them as a
cleanup side effect:

- scanner scoring, selection, thresholds, ranking, sorting, and fallback/live
  labels;
- backtest math, fills, costs, metrics, benchmark semantics, and stored result
  readback;
- portfolio accounting, cash, holdings, P&L, FX/native currency, cost basis,
  sync/import/replay, and mutation semantics;
- provider order, live-call paths, fallback behavior, circuit behavior,
  MarketCache TTL/SWR/cold-start, stale labels, cache keys, and payload meaning;
- AI prompts, model routing, decision thresholds, recommendation semantics,
  evidence weighting, retries, and cost/quota logic;
- auth/RBAC/security dependencies, capabilities, sessions, CSRF/CORS,
  password/token handling, and admin protection;
- notification routing, send behavior, thresholds, and retries;
- DuckDB/PostgreSQL source-of-truth boundaries;
- Options Lab ranking, gates, no-trade policy, recommendation policy, payoff
  math, and API response shape;
- API response shapes and stored contract versions.

Source:

- [Backend Protected Domains](./codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md)
- [Codex Standard Guard](./codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md)

## Frontend Linear OS Architecture

WolfyStock frontend routes should follow the Linear OS product language:

- one dominant console, board, table, chart, or workbench per route;
- root canvas and route width owned by the shared shell;
- rows, tables, strips, rails, drawers, and disclosures before cards;
- diagnostics and raw provider/schema/debug detail collapsed by default on
  user routes;
- Chinese-first user-facing labels except tickers, provider names, metrics,
  currency codes, and accepted domain terms;
- no pure-black gutters, card-first dashboards, generic admin layout on
  product routes, decorative effects, fake charts, or raw internal leakage.

New user-facing work should prefer `apps/dsa-web/src/components/linear/`.
Existing `Terminal*` names are compatibility adapters and must render Linear
OS material.

Source:

- [Linear OS Design Language](./codex/WOLFYSTOCK_LINEAR_OS_DESIGN_LANGUAGE.md)
- [Frontend Surface Usage](./codex/WOLFYSTOCK_FRONTEND_SURFACE_USAGE.md)
- [Frontend Route Templates](./codex/WOLFYSTOCK_FRONTEND_ROUTE_TEMPLATES.md)
- [Terminal Primitives Usage](./codex/WOLFYSTOCK_TERMINAL_PRIMITIVES_USAGE.md)
- [Canonical UI Primitives](./design/wolfystock-canonical-ui-primitives.md)

## Provider And Data Architecture

Provider runtime owns provider ordering, fallback, retry/circuit posture,
freshness labels, optional enrichment budgets, source disclosure, sanitized
diagnostics, and cache/local-first behavior.

Rules:

- Prefer local/cache-first paths where current behavior already does so.
- Do not reorder providers or deepen fallback without explicit approval.
- Do not label fallback, stale, delayed, synthetic, fixture, repaired, mock, or
  inferred data as live.
- Keep required data and optional enrichment separate.
- Treat provider capability metadata and advisory planning as inert unless a
  task explicitly wires runtime behavior.
- Keep raw provider payloads, request URLs, headers, credentials, API keys,
  tokens, query strings, and stack traces out of normal logs, docs, UI, and
  evidence.

Source docs:

- [Provider Data Freshness Reliability Guide](./audits/provider-data-freshness-reliability-guide.md)
- [Provider Capability Metadata](./operations/provider-capability-metadata.md)
- [Market Data Provider Upgrade Decision Matrix](./audits/market-data-provider-upgrade-decision-matrix.md)
- [Provider Data Incident Runbook](./audits/provider-data-incident-runbook.md)
- [Provider Budget And Routing Rules](./codex/WOLFYSTOCK_PROVIDER_BUDGET_AND_ROUTING_RULES.md)

## MarketCache, Freshness, Fallback, And SWR

MarketCache is a protected provider-runtime boundary. Current docs describe it
as process-local and governed by TTL, stale-while-revalidate, cold-start
fallback, background refresh, freshness metadata, and explicit fallback/stale
labels.

Safe maintenance rules:

- Do not change TTL, SWR, cold-start fallback, background refresh, cache keys,
  cache identity, or payload meaning unless explicitly scoped.
- Do not hide stale/cache-only/degraded labels to make a UI look cleaner.
- During provider incidents, prefer reducing outbound pressure and preserving
  stale/cache-only disclosure over widening live fallback chains.
- If a future shared cache is proposed, preserve current TTL, stale serving,
  background refresh, cold-start fallback, source identity, owner/session scope
  where needed, and no-secret cache metadata.

Source docs:

- [Provider Data Freshness Reliability Guide](./audits/provider-data-freshness-reliability-guide.md)
- [Provider Data Incident Runbook](./audits/provider-data-incident-runbook.md)
- [WS2 multi-user runtime cost control design](./audits/ws2-multi-user-runtime-cost-control-design.md)
- [Backend Protected Domains](./codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md)

## Domain Guide

### Scanner And Watchlist

Scanner is a bounded discovery layer, not a trading engine. It owns universe
construction, deterministic ranking, candidate diagnostics, shortlist
persistence, watchlist handoff, and optional AI interpretation.

Do not change score/order/thresholds, market profiles, deterministic ranking,
or scanner-to-backtest handoff unless explicitly scoped and regression-tested.
AI remains additive interpretation, not primary ranking.

Start with:

- [Market Scanner](./market-scanner.md)
- [Scanner export label policy](./product/wolfystock-scanner-export-label-policy.md)
- `api/v1/endpoints/scanner.py`
- `src/services/market_scanner_service.py`
- `apps/dsa-web/src/pages/ScannerSurfacePage.tsx`
- `apps/dsa-web/src/pages/WatchlistPage.tsx`

### Market Overview, Liquidity, And Rotation

Market routes are operator context surfaces. They must preserve truthful source
and freshness labels and keep source/runtime diagnostics collapsed unless the
route is admin/operator-focused.

Start with:

- `api/v1/endpoints/market_overview.py`
- `api/v1/endpoints/market.py`
- `api/v1/endpoints/liquidity_monitor.py`
- `apps/dsa-web/src/pages/MarketOverviewPage.tsx`
- `apps/dsa-web/src/pages/LiquidityMonitorPage.tsx`
- `apps/dsa-web/src/pages/MarketRotationRadarPage.tsx`
- [Provider Data Freshness Reliability Guide](./audits/provider-data-freshness-reliability-guide.md)

### Portfolio

Portfolio owns accounts, holdings, cash, transactions, P&L, FX/native currency,
cost basis, broker sync/import overlays, ledger mutations, and read
projections.

UI work must not independently recalculate accounting authority. Backend work
must preserve mutation/read boundaries and owner attribution.

Start with:

- `api/v1/endpoints/portfolio.py`
- `src/services/portfolio_service.py`
- `src/repositories/portfolio_repo.py`
- `apps/dsa-web/src/pages/PortfolioPage.tsx`
- [Phase F decisions](./architecture/phase-f/decisions.md)
- [Phase F status](./architecture/phase-f/status.md)

### Options Lab

Options Lab is an ExperimentConsole, not an execution surface. Current provider
contracts describe fixture/dry-run posture and disabled live adapters unless a
future task explicitly approves staged wiring.

Do not add order/broker/portfolio mutation paths. Do not weaken fail-closed
data-quality gates, liquidity gates, no-trade policy, ranking, payoff math, or
recommendation policy.

Start with:

- `api/v1/endpoints/options.py`
- `apps/dsa-web/src/pages/OptionsLabPage.tsx`
- [Options provider adapter contract](./audits/options-provider-adapter-contract.md)
- [Options Lab phase 0 design](./audits/options-lab-phase0-design.md)
- [Trading no-advice product policy](./audits/trading-no-advice-product-policy.md)

### Backtest

Backtest owns standard and rule backtest execution, calculation math, stored
readback, support exports, compare workflows, universe diagnostics, and
professional-readiness disclosures.

Do not change calculations, fills, costs, metrics, benchmark semantics,
stored-first readback authority, or local-only universe execution unless a task
explicitly scopes that change.

Start with:

- [Backtest System](./backtest-system.md)
- [Backtest helper maintenance](./backtest-helper-maintenance.md)
- `api/v1/endpoints/backtest.py`
- `src/services/backtest_service.py`
- `src/services/rule_backtest_service.py`
- `apps/dsa-web/src/pages/BacktestPage.tsx`
- `apps/dsa-web/src/pages/DeterministicBacktestResultPage.tsx`
- `apps/dsa-web/src/pages/RuleBacktestComparePage.tsx`

### Admin Logs, Provider Ops, Auth, RBAC, And Security

Admin/Ops surfaces may show technical detail, but details must be layered,
sanitized, and collapsed when raw. Normal user routes must not expose admin
implementation language.

Auth/RBAC/security changes are protected. Do not alter sessions, capabilities,
CSRF/CORS, password/token handling, or admin protection as a side effect.

Start with:

- [Auth/RBAC release security guide](./audits/auth-rbac-release-security-guide.md)
- [Admin RBAC capability model](./audits/admin-rbac-capability-model-design.md)
- [Admin governance cost E2E QA runbook](./audits/admin-governance-cost-e2e-qa-runbook.md)
- [Production security hardening audit](./audits/production-security-hardening-audit.md)
- `api/deps.py`
- `api/v1/endpoints/auth.py`
- `api/v1/endpoints/admin_*.py`
- `apps/dsa-web/src/pages/AdminLogsPage.tsx`
- `apps/dsa-web/src/pages/AdminUsersPage.tsx`
- `apps/dsa-web/src/pages/AdminProviderCircuitDiagnosticsPage.tsx`
- `apps/dsa-web/src/pages/MarketProviderOperationsPage.tsx`

## Data Stores And Optional Engines

PostgreSQL is the business database direction for users, portfolio accounting,
watchlists, admin logs, settings, analysis tasks, and backtest metadata, with
SQLite/fallback/coexistence paths still documented in architecture materials.

DuckDB is optional, disabled by default, and diagnostic-only. It must not become
scanner, backtest, or portfolio runtime truth without a separate approved
production proposal.

Start with:

- [Database component map](./architecture/database-component-map.md)
- [Database maintenance handbook](./architecture/database-maintenance-handbook.md)
- [PostgreSQL baseline design](./architecture/postgresql-baseline-design.md)
- [Quant DuckDB Engine](./quant-duckdb-engine.md)
- [DuckDB Operator Smoke Guide](./operations/duckdb-operator-smoke-guide.md)
- [DuckDB Production Readiness Checklist](./operations/duckdb-production-readiness-checklist.md)

## Test And Validation Strategy

Validation should match the change surface.

| Change type | Default validation |
| --- | --- |
| Docs-only | `git diff --check -- <changed docs>`, `bash scripts/release_secret_scan.sh`, status/diff checks |
| Python backend | Focused pytest/compile, then wider gates if shared runtime or protected semantics changed |
| Frontend UI | Focused Vitest, lint/build/design guard, browser proof on route/viewports |
| API/schema/auth | Backend focused tests plus affected client build/tests |
| Provider/cache | Provider/cache/freshness tests and no live-provider proof unless explicitly scoped |
| Release/landing | Full gates required by launch/release docs |

Current validation authority:

- [Codex Standard Guard](./codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md)
- [Codex Task Runtime Rules](./codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md)
- [Frontend Validation Playbook](./codex/WOLFYSTOCK_FRONTEND_VALIDATION_PLAYBOOK.md)
- [Visual Evidence Protocol](./codex/WOLFYSTOCK_CODEX_VISUAL_EVIDENCE_PROTOCOL.md)
- [CI Gate Usage](./audits/ci-gate-usage.md)

## Local Troubleshooting Commands

Use current repo-supported commands and avoid installing dependencies unless
the task explicitly requires dependency refresh.

Backend:

```bash
python main.py --serve-only
uvicorn server:app --reload --host 0.0.0.0 --port 8000
./scripts/ci_gate.sh
python3 -m py_compile <changed_python_files>
python3 -m pytest -q <focused_tests>
```

Web:

```bash
cd apps/dsa-web
npm run lint
npm run build
npm run check:design
```

Docs-only:

```bash
git diff --check -- <changed-doc-files>
bash scripts/release_secret_scan.sh
git status --short --branch
git diff --name-only
git diff --cached --name-only
```

Backtest smoke:

```bash
python3 scripts/smoke_backtest_standard.py
python3 scripts/smoke_backtest_rule.py
```

DuckDB diagnostics:

```bash
# See docs/operations/duckdb-operator-smoke-guide.md before running.
```

## Safe Modification Guide By Module

Before changing a module, answer:

- Which domain owns this behavior?
- Is it a protected domain?
- What is the public contract or facade?
- What must remain unchanged?
- What focused tests or browser proof will detect regression?
- Which docs need updates if user-visible behavior, API behavior, deployment,
  notification, report shape, or maintenance workflow changes?

| Module | Read first | Safe default |
| --- | --- | --- |
| Frontend route | Route page, route tests, Linear OS docs | Preserve route surface taxonomy, shell ownership, API calls, auth gates, and browser proof expectations |
| API endpoint | Endpoint, schemas, service, tests | Preserve response shape and capability dependencies unless explicitly scoped |
| Service | Service, repository, domain docs, tests | Add small contract-preserving changes; avoid cross-domain internals |
| Provider | Provider docs, protected domains, tests | Preserve order/fallback/freshness/live labels and sanitize diagnostics |
| Scanner | Scanner docs, service, endpoint, route tests | Do not change scoring/order/thresholds without explicit task scope |
| Backtest | Backtest docs, rule/standard services, fixtures | Preserve math and stored-first readback |
| Portfolio | Portfolio service/repo, Phase F docs, tests | Preserve accounting and mutation semantics |
| Auth/admin | Auth/RBAC docs, dependencies, capability tests | Preserve enforcement; keep dangerous details collapsed/sanitized |
| Docs | Current index/authority docs | Link to source docs; avoid deleting/moving archives unless explicitly scoped |

## Source-Of-Truth Doc Map

Use [Docs Index](./DOCS_INDEX.md) as the navigation start. The most important
source-of-truth documents are:

- [README](../README.md)
- [WolfyStock System Handbook](./WOLFYSTOCK_SYSTEM_HANDBOOK.md)
- [WolfyStock AI Maintenance Manual](./WOLFYSTOCK_AI_MAINTENANCE_MANUAL.md)
- [WolfyStock Modular Architecture Manual](./architecture/WOLFYSTOCK_MODULE_ARCHITECTURE.md)
- [Backend / Frontend Modular Maintenance Handbook](./architecture/backend-frontend-modular-maintenance-handbook.md)
- [Codex Standard Guard](./codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md)
- [Codex Task Runtime Rules](./codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md)
- [Backend Protected Domains](./codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md)
- [Linear OS Design Language](./codex/WOLFYSTOCK_LINEAR_OS_DESIGN_LANGUAGE.md)
- [Audit Index](./audits/README.md)
- [Archive Index](./ARCHIVE_INDEX.md)

## What This Handbook Intentionally Does Not Do

- It does not approve route migrations as complete.
- It does not approve public launch or change the current launch verdict.
- It does not move, delete, or archive tracked docs.
- It does not replace current route/API/source inspection.
- It does not authorize protected-domain changes.
- It does not make DuckDB production runtime truth.
- It does not turn historical audit docs into current authority.
