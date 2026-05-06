# WolfyStock Global Codebase Audit

Status: Partial
Owner domain: Frontend and repo-wide audit
Related docs: `docs/audits/wolfystock-frontend-design-conformance-audit.md`, `docs/audits/markdown-inventory.md`

Date: 2026-05-05 Asia/Shanghai
Repository: `/Users/yehengli/daily_stock_analysis`
Branch audited: `main`
Mode: read-only audit document, no product-code changes

## 1. Executive summary

Current repo health: **stable but complexity-heavy**. The requested preflight confirmed the checkout is on `main`, upstream is aligned with `origin/main`, and the current dirty files are concentrated in an unrelated DuckDB Quant Engine Phase 2 area. This audit did not modify those files.

The biggest current risks are:

- Large frontend page modules and backend service modules have become high-friction edit surfaces.
- Status, freshness, provider, severity, and quality labels are mapped repeatedly across frontend pages, frontend primitives, API schemas, and backend services.
- The frontend build passes, but still emits a large chunk warning for a 1.19 MB minified chunk and a 520.95 kB CSS bundle.
- The design guard passes, but reports 103 warning-only findings, mostly native input/select/button risks in backtest and related workflow surfaces.
- Backend service/API growth has expanded hot paths around market provider fallback, scanner/watchlist batching, report/history normalization, admin logs, and optional DuckDB diagnostics.

Safest next optimizations:

- Start with no-code inventory cleanup and verification, then consolidate low-risk frontend status/freshness helpers.
- Split only the most obvious page-local rendering helpers from very large frontend pages, without changing business behavior.
- Add focused tests around shared status/freshness mapping before moving call sites.
- Profile before deeper backend cache or architecture changes.

What should not be changed yet:

- Do not delete Phase A-G PostgreSQL coexistence shims, legacy compatibility aliases, scanner/backtest separation, or DuckDB optional-service boundaries.
- Do not merge scanner into backtest.
- Do not make DuckDB part of production scanner/backtest/portfolio runtime.
- Do not turn design-guard warnings into blocking CI without a visual cleanup pass.
- Do not refactor `src/storage.py`, scanner, portfolio, or rule backtest broadly without a separate phased plan and targeted tests.

## 2. Methodology

Commands run:

```bash
cd /Users/yehengli/daily_stock_analysis
pwd
git branch --show-current
git status --short
git status --branch --short
git log --oneline -30
./scripts/task_preflight.sh
git ls-files | wc -l
git ls-files --others --exclude-standard
find . -maxdepth 3 -type d \( -name "__pycache__" -o -name ".pytest_cache" -o -name "coverage" -o -name "test-results" -o -name "playwright-report" \) 2>/dev/null
find . -maxdepth 4 -type f | grep -E "(\.duckdb|\.duckdb\.wal|\.db|\.sqlite|\.log|\.tmp)$" || true
python3 -m compileall -q src api
python3 -m pytest --collect-only -q
```

Frontend commands:

```bash
cd /Users/yehengli/daily_stock_analysis/apps/dsa-web
npm run check:design
npm run lint
npm run build
npm run test -- --help
find src -type f \( -name "*.tsx" -o -name "*.ts" \) | wc -l
find src -type f -name "*.tsx" -exec wc -l {} + | sort -nr | head -30
```

Static inspection included:

- Mandatory docs: `CODEX_FRONTEND_DESIGN_CONSTITUTION.md`, `docs/operations/parallel-codex-playbook.md`, `docs/checks/ci-gate-clarity.md`, `docs/checks/design-guard.md`, `docs/quant-duckdb-engine.md`, `docs/operations/duckdb-operator-smoke-guide.md`.
- Frontend source under `apps/dsa-web/src`.
- Backend/API source under `src` and `api`.
- API schemas under `api/v1/schemas`.
- Existing architecture/audit docs under `docs/architecture` and `docs/qa`.

Limitations:

- No browser verification was required or run.
- No dev servers were started or stopped.
- No full `./scripts/ci_gate.sh` was run because this is docs-only and the worktree contains unrelated parallel DuckDB edits.
- No package installs, global tooling installs, destructive cleanup, provider ingestion, scanner/backtest batch operations, or DuckDB full-market ingest were run.
- No dead-code tool such as `vulture`, `ts-prune`, or `knip` was installed or run. Unused-code claims below are therefore conservative.

## 3. Current system map

| Surface | Primary areas | Current shape | Audit note |
| --- | --- | --- | --- |
| Home/report/history | `HomeBentoDashboardPage.tsx`, `src/services/analysis_service.py`, `src/services/history_service.py`, `api/v1/endpoints/analysis.py`, `api/v1/endpoints/history.py` | Analysis orchestration, decision trace, report quality, history detail normalization | Strong functionality, but repeated report/trace normalization exists across backend and frontend. |
| Market Overview | `MarketOverviewPage.tsx`, `src/services/market_overview_service.py`, `api/v1/endpoints/market.py`, market primitives | Cached/fallback market panels with provider health and freshness labels | Freshness/provider semantics are important and should stay honest; helper consolidation should be cautious. |
| Scanner | `UserScannerPage.tsx`, `ScannerSurfacePage.tsx`, `src/services/market_scanner_service.py`, `src/services/market_scanner_ops_service.py`, scanner schemas | Deterministic scanner primary, AI interpretation additive | Large frontend and backend surfaces; do not merge into backtest. |
| Watchlist | `WatchlistPage.tsx`, `src/services/watchlist_service.py`, watchlist API/schema | Owner-scoped watchlist and saved scanner intelligence | Shares scanner status concepts but has separate UI mapping. |
| Backtest | `BacktestPage.tsx`, `DeterministicBacktestResultPage.tsx`, backtest components, `src/services/backtest_service.py`, `src/services/rule_backtest_service.py` | Deterministic and rule backtest workflows with large result/report surfaces | Functionally covered, but largest build/page risks are here. |
| Portfolio | `PortfolioPage.tsx`, `src/services/portfolio_service.py`, portfolio repo/schema | Owner-scoped accounts, trades, cash, corporate actions, analytics and risk explainability | Large service/page; optimization should preserve accounting formulas. |
| Admin logs/notifications | `AdminLogsPage.tsx`, `AdminNotificationsPage.tsx`, `NotificationChannelsConfig.tsx`, `ExecutionLogService` | Audit/observability and notification routing | Strong tests exist, but status/severity labels overlap with shared badge logic. |
| Settings/system health | `SettingsPage.tsx`, system settings components, `src/services/system_config_service.py`, config registry/schema | Admin control plane, config validation, runtime health, curated editors | Very large page; keep raw config suppression and `.env` compatibility intact. |
| DuckDB quant engine | `src/services/quant_analytics/duckdb_service.py`, `api/v1/endpoints/quant.py`, `api/v1/schemas/quant.py`, docs/tests | Optional, disabled-by-default diagnostics accelerator | Current dirty files are in this area; audit treats them as parallel work. Do not connect to production paths yet. |
| Frontend design guard / CI tooling | `apps/dsa-web/scripts/check-design-constitution.mjs`, `scripts/task_preflight.sh`, `scripts/ci_gate.sh` | Separate design guard and backend gate clarity | Guard works as warning-first tool; keep separate from backend gate unless explicitly changed. |

## 4. Confirmed findings

### CF-01. Large frontend page modules are high-risk edit surfaces

Evidence:

- `find src -type f -name "*.tsx" -exec wc -l {} + | sort -nr | head -30` in `apps/dsa-web` reported 77,957 total TSX lines.
- Largest page files include `SettingsPage.tsx` 5,007 lines, `UserScannerPage.tsx` 4,553, `HomeBentoDashboardPage.tsx` 3,929, `PortfolioPage.tsx` 2,925, `MarketOverviewPage.tsx` 2,472, `ChatPage.tsx` 2,017, `AdminLogsPage.tsx` 1,923, `BacktestPage.tsx` 1,414.

Affected areas:

- Settings/system health, Scanner, Home/report/history, Portfolio, Market Overview, Chat, Admin Logs, Backtest.

Impact: high.
Risk: medium.

Recommendation:

- Do not split pages mechanically.
- Start by extracting pure, tested display helpers and repeated label/status functions from the largest pages.
- Keep route DOM skeletons and product workflows stable during extraction.

Suggested tests:

- Existing page tests for each touched page.
- `npm run check:design`, `npm run lint`, `npm run build`.
- Browser checks only for visible UI refactors, not for pure helper moves.

### CF-02. Backend service modules are large enough to hide coupling and performance risks

Evidence:

- `find src api -type f -name "*.py" -exec wc -l {} + | sort -nr | head -40` reported 123,280 total Python lines.
- Largest backend/API files include `src/services/rule_backtest_service.py` 9,370 lines, `src/storage.py` 7,038, `src/services/market_scanner_service.py` 5,696, `src/core/pipeline.py` 4,574, `src/services/portfolio_service.py` 4,515, `src/services/report_renderer.py` 4,134, `src/core/rule_backtest_engine.py` 4,097, `src/services/execution_log_service.py` 3,784, `src/search_service.py` 3,183, `src/services/market_overview_service.py` 2,543.

Affected areas:

- Rule backtest, storage/coexistence, scanner, analysis pipeline, portfolio, report rendering, execution logs, search, market overview.

Impact: high.
Risk: high for broad rewrites, low for targeted helper extraction.

Recommendation:

- Treat large files as optimization targets only when size aligns with repeated logic, hot-path cost, or test fragility.
- Avoid broad service rewrites before profiling and focused regression coverage.

Suggested tests:

- Domain-specific pytest modules before and after any extraction.
- `python3 -m py_compile <changed files>`.
- Full `./scripts/ci_gate.sh` only when product code changes are complete and parallel dirty work is not blocking interpretation.

### CF-03. Frontend status and label mapping is duplicated across shared and page-local helpers

Evidence:

- `apps/dsa-web/src/components/ui/StatusBadge.tsx` defines `UnifiedStatus`, `normalizeStatus`, `getStatusLabel`, and `getStatusTone`.
- `apps/dsa-web/src/components/market-overview/marketOverviewPrimitives.tsx` defines separate `FRESHNESS_LABELS`, `STATUS_LABELS`, `FRESHNESS_CLASSES`, and provider/freshness resolution helpers.
- `apps/dsa-web/src/pages/UserScannerPage.tsx` defines `normalizeRunState`, `compactScannerStateLabel`, `sanitizeScannerErrorSummary`, and scanner provider/fallback labels.
- `apps/dsa-web/src/pages/AdminNotificationsPage.tsx` defines local `statusLabel` and `statusTone`.
- `rg` also found repeated status/freshness/severity mapping in `AdminLogsPage`, backtest shared components, scanner types, watchlist types, and market overview tests.

Affected areas:

- Scanner, Market Overview, Admin Notifications, Admin Logs, Backtest, Watchlist, shared UI badges.

Impact: medium.
Risk: medium.

Recommendation:

- Create a small shared status vocabulary only after adding tests for current labels.
- Preserve domain-specific labels where they carry product meaning, especially provider freshness vs execution status.

Suggested tests:

- `StatusBadge.test.tsx`
- `MarketOverviewPage.test.tsx` provider health badge states
- `UserScannerPage.test.tsx` status/failure labels
- `AdminNotificationsPage.test.tsx`
- Backtest result report tests

### CF-04. API/schema status fields are broad and inconsistent by design, but now need an explicit shared vocabulary

Evidence:

- `api/v1/schemas/analysis.py` has `TaskStatusEnum` plus several raw string status fields and regex patterns.
- `api/v1/schemas/backtest.py` contains many `status: str`, `status_message`, `status_history`, `fallback_used`, and `data_quality` fields.
- `api/v1/schemas/scanner.py` uses both `Literal["selected", "rejected", "data_failed", "skipped", "error", "evaluated"]` and multiple raw string statuses.
- `api/v1/schemas/quant.py` uses raw `status: str`, `dataMode`, and factor data-mode strings.
- `api/v1/schemas/portfolio.py` defines literal FX statuses separately from portfolio connection statuses.
- `apps/dsa-web/src/types/*` mirrors many of these as separate TS unions or raw strings.

Affected areas:

- API schemas, frontend API/types, status badges, tests.

Impact: medium.
Risk: medium.

Recommendation:

- Do not force one enum across all domains.
- Define a small cross-domain display status contract such as `success | failed | error | running | pending | partial | skipped | unknown | cancelled | warning | info | disabled`.
- Keep domain enums as source-of-truth where they are semantically narrower.

Suggested tests:

- Schema serialization tests for touched APIs.
- Frontend type and label tests.
- API route contract tests where status fields are returned.

### CF-05. Frontend build passes but has a confirmed chunk-size warning

Evidence:

- `npm run build` passed.
- Vite output included `index-CKOZGjeY.js` at 1,197.07 kB minified / 400.94 kB gzip and warned: "Some chunks are larger than 500 kB after minification."
- Other large route chunks included `BacktestPage` 233.00 kB, `SystemSettingsPage` 205.18 kB, `ScannerSurfacePage` 148.01 kB, `HomeBentoDashboardPage` 132.13 kB, and `MarketOverviewPage` 112.72 kB.
- CSS bundle was 520.95 kB minified / 74.08 kB gzip.

Affected areas:

- Frontend route loading, initial JS/CSS transfer, long-term route chunking.

Impact: medium.
Risk: low for measurement, medium for code-splitting changes.

Recommendation:

- Add bundle inspection as a no-code Phase 0 task.
- Consider manual chunks only after identifying what is inside the large `index` chunk.
- Prefer route-level lazy imports and heavy component isolation before changing Rollup chunk config.

Suggested tests:

- `npm run build`.
- Route smoke tests after any lazy-import changes.

### CF-06. Design guard passes but warning volume remains high

Evidence:

- `npm run check:design` passed with 103 warnings across 213 scanned files.
- First warnings are native UI findings in `DeterministicBacktestFlow.tsx`, `HistoricalEvaluationPanel.tsx`, `NormalBacktestWorkspace.tsx`, and `ProBacktestWorkspace.tsx`.
- The guard explicitly says warning-only findings are advisory and should be reviewed during visual QA.

Affected areas:

- Backtest workflow controls first, then other legacy surfaces.

Impact: medium.
Risk: low for audit, medium for visible cleanup.

Recommendation:

- Keep warning-only posture.
- Tackle native UI warnings in small surface-specific passes.
- Do not make design guard warnings blocking until current warnings are intentionally burned down.

Suggested tests:

- `npm run check:design`.
- Affected page/component tests.
- Browser desktop and 390px checks for visible UI cleanup.

### CF-07. Repository hygiene is mostly clean for tracked/untracked files, but ignored runtime artifacts exist locally

Evidence:

- `git ls-files | wc -l` reported 1006 tracked files.
- `git ls-files --others --exclude-standard` produced no output.
- Cache directory search found `.pytest_cache`, many `__pycache__` directories, and ignored venv cache directories.
- Runtime artifact search found `logs/api_server_20260504.log`, `logs/api_server_20260505.log`, `logs/api_server_debug_20260505.log`, `logs/api_server_debug_20260504.log`, and `data/stock_analysis.db`.

Affected areas:

- Local workspace hygiene, not tracked product code.

Impact: low.
Risk: low.

Recommendation:

- No deletion in this audit.
- Keep generated logs/databases ignored and out of commits.
- Consider a future no-code operator cleanup checklist, not automatic cleanup.

Suggested tests:

- `git ls-files --others --exclude-standard`.
- `git status --short`.

### CF-08. Test surface is broad and collectable

Evidence:

- `python3 -m pytest --collect-only -q` collected 1996 tests successfully.
- `find tests -type f -name "test*.py" | wc -l` reported 168 Python test files.
- Frontend Vitest CLI help is available through `npm run test -- --help`.

Affected areas:

- CI/test planning.

Impact: high positive.
Risk: low.

Recommendation:

- Prefer targeted tests by product surface, then widen.
- Keep `ci_gate` interpretation separate from design guard and browser verification.

Suggested tests:

- Use the targeted matrix in `docs/checks/ci-gate-clarity.md`.

## 5. Potential findings requiring verification

### PF-01. Some frontend route chunks may be carrying shared libraries that should be lazily isolated

Evidence:

- Build output has a 1.19 MB minified `index` chunk and multiple large route chunks.
- Static file size evidence alone does not identify the exact contents.

Uncertainty:

- Needs bundle analyzer or Vite/Rollup chunk inspection before deciding whether chart, markdown, icon, preview fixture, or shared app code is the driver.

Recommendation:

- Run a bundle composition analysis in a dedicated frontend tooling session.
- Do not adjust manual chunks blindly.

### PF-02. Large page render paths may repeatedly normalize/sort/filter during render

Evidence:

- Static searches found dense `map`, `filter`, `sort`, `JSON.stringify`, and normalization logic in `HomeBentoDashboardPage.tsx`, `ChatPage.tsx`, `UserScannerPage.tsx`, `RuleBacktestComparePage.tsx`, `DeterministicBacktestResultPage.tsx`, and report components.
- Several pages already use `useMemo`, so this is not uniformly bad.

Uncertainty:

- Needs React profiler or route-specific render timing to distinguish real regressions from harmless small-list work.

Recommendation:

- Profile only the largest visible routes before memoization changes.
- Avoid adding `useMemo` everywhere as a style rule.

### PF-03. Backend hot paths may still have duplicated market-provider fallback and serialization costs

Evidence:

- Static search shows substantial fallback/provider/caching logic in `src/services/market_overview_service.py`, `src/search_service.py`, `src/services/market_scanner_service.py`, and data provider layers.
- Existing tests cover many fallback cases, but this audit did not run provider load tests.

Uncertainty:

- Needs request timing or instrumentation under representative provider failures.

Recommendation:

- Keep current fallback safety.
- Profile provider failure/cold-cache paths before consolidating.

### PF-04. DuckDB Phase 2 may be active but unfinished in another session

Evidence:

- Preflight dirty files include `api/v1/endpoints/quant.py`, `api/v1/schemas/quant.py`, `docs/quant-duckdb-engine.md`, `docs/operations/duckdb-operator-smoke-guide.md`, `src/services/quant_analytics/duckdb_service.py`, and quant tests.

Uncertainty:

- This audit did not inspect uncommitted diffs in detail and did not modify or stage those files.

Recommendation:

- Treat DuckDB optimization separately.
- Preserve disabled/no-write behavior and diagnostic-only scope.

### PF-05. Some older docs may overlap or be stale, but they are not confirmed obsolete

Evidence:

- Existing audit/roadmap docs include `docs/architecture/system-optimization-audit.md`, `docs/architecture/system-optimization-roadmap.md`, `docs/architecture/wolfystock-frontend-visual-constitution-audit.md`, and `docs/qa/full-stack-usability-audit-2026-05-01.md`.

Uncertainty:

- Older docs may still be useful historical evidence. No docs index was updated in this task.

Recommendation:

- Add a future docs inventory pass if operators need a canonical audit index.
- Do not delete or archive existing docs from this audit alone.

## 6. Duplicate/redundant code candidates

| Candidate | Classification | Evidence | Recommendation |
| --- | --- | --- | --- |
| Generic execution status display | confirmed duplicate | `StatusBadge.tsx`, `AdminNotificationsPage.tsx`, `AdminLogsPage.tsx`, backtest shared helpers | Consolidate only generic execution statuses first. |
| Market freshness/provider labels | intentional domain-specific overlap | `marketOverviewPrimitives.tsx` and backend market provider health fields | Keep separate from generic execution status, but expose a tested adapter. |
| Scanner run/failure labels | confirmed duplicate with domain nuance | `UserScannerPage.tsx` maps `provider_error`, `fallback`, `local_data`, `partial`, `unknown` separately | Move to scanner utility only after preserving Chinese/English copy. |
| Developer-details panels | likely duplicate | Home, Scanner, Watchlist, Settings, Admin Notifications, Backtest report all use "开发者细节" patterns | Create a shared collapsed diagnostics component later, preserving per-surface copy. |
| Result quality/report status labels | likely duplicate | Backend `report_quality`, frontend `ReportQuality*` types, Home quality chips | Consolidate after Home/report history tests lock current labels. |
| Command/action bar chips | likely duplicate | Market command chips, Scanner chips, Backtest compare chips, product chip classes | Treat as design-system cleanup, not behavior cleanup. |
| API schema status fields | confirmed overlap | `analysis.py`, `backtest.py`, `scanner.py`, `quant.py`, `admin_logs.py`, `admin_notifications.py` | Add a display-status glossary, not a single universal enum. |
| Notification channel settings surfaces | acceptable redundancy for now | Dedicated `AdminNotificationsPage` plus embedded `NotificationChannelsConfig` in Settings | Keep until admin IA decides whether one surface owns notification routing. |

## 7. Dead code / obsolete file candidates

No confirmed unused product source file was identified with enough evidence to delete in this audit.

Candidates and observations:

| Item | Classification | Evidence | Recommendation |
| --- | --- | --- | --- |
| Local caches/logs/database files | confirmed generated local artifacts | Ignored `__pycache__`, `.pytest_cache`, `logs/*.log`, `data/stock_analysis.db`; no unignored untracked files | Do not commit. Optional local cleanup only with operator approval. |
| Existing older audit docs | likely intentional historical docs | Several prior audit/roadmap docs exist under `docs/architecture` and `docs/qa` | Keep unless a docs inventory pass creates a canonical archive/index. |
| `ScannerSurfacePage.tsx` wrapper | intentional route wrapper candidate | Imports and returns `UserScannerPage`; tested via `ScannerSurfacePage.test.tsx` | No action unless route structure changes. |
| `StatusBadge` plus domain badges | acceptable redundancy with consolidation candidate | Used by Admin Logs, Backtest, Data Source config; market has separate freshness badge | Do not remove; consolidate gradually. |
| Old `api/v1/endpoints/health.py` dead endpoint from prior audits | no-action-needed observation | File is absent now; live health endpoints are in `api/app.py` | No current cleanup needed. |

## 8. Performance risk register

### Frontend risks

| Risk | Classification | Evidence | Priority | Recommendation |
| --- | --- | --- | --- | --- |
| Large initial chunk | confirmed | Vite warning; `index-CKOZGjeY.js` 1,197.07 kB minified | P1 | Bundle analysis, then targeted lazy isolation. |
| Large CSS bundle | confirmed | `index-BH5tm17d.css` 520.95 kB minified | P2 | Audit global CSS/token duplication after UI stabilization. |
| Large page components | confirmed | Largest TSX pages 1,400-5,000 lines | P1 | Extract pure helpers/components by route, not broad rewrites. |
| Repeated render-time normalization | needs verification | Dense map/filter/sort/normalization in large pages | P2 | Profile before adding memoization. |
| Heavy chart/report rendering | likely issue | Backtest result/report and report chart modules are large | P2 | Lazy-load report/chart-only sections where route tests permit. |
| Large drawers rendering full content | likely issue | Full report/backtest/admin details drawers include rich content | P2 | Verify whether drawers mount all content by default before changing. |
| localStorage hydration loops | no-action-needed observation for now | `ThemeProvider` uses localStorage in a small controlled scope | P3 | No action unless profiler shows hydration churn. |
| Design guard native UI warnings | confirmed UX/perf-adjacent | 103 warning-only findings | P2 | Surface-specific UI cleanup with browser checks. |

### Backend risks

| Risk | Classification | Evidence | Priority | Recommendation |
| --- | --- | --- | --- | --- |
| Market provider cold/failure paths | likely issue | Market/cache/fallback code is broad and tested, but provider failures are expensive by nature | P1 | Add timing instrumentation before changing cache semantics. |
| Scanner/backtest/watchlist batch bounds | likely issue | Scanner/watchlist/backtest surfaces support batch-like operations | P1 | Verify caps, dedupe, and concurrency with focused tests before optimization. |
| Report/history JSON normalization | likely issue | Decision trace and report quality are built/read in analysis/history/frontend | P2 | Consolidate normalization after contract tests. |
| Search/news provider retries | likely issue | `src/search_service.py` contains many provider retry/fallback paths | P2 | Profile search dimensions before refactor. |
| DuckDB accidental writes | controlled but high impact | Docs state disabled no-write is mandatory; quant files are currently dirty in another session | P0 for DuckDB sessions | Preserve disabled no-write tests before Phase 2 changes. |
| Storage manager complexity | confirmed architecture risk | `src/storage.py` 7,038 lines and central coexistence role | P2 | Do not rewrite broadly; peel off bounded repository paths. |

## 9. Test and CI gaps

Current checks run in this audit:

- `./scripts/task_preflight.sh` passed and reported branch/upstream/dirty-file context.
- `npm run check:design` passed with 103 warnings.
- `npm run lint` passed.
- `npm run build` passed with Vite chunk warning.
- `python3 -m compileall -q src api` passed.
- `python3 -m pytest --collect-only -q` collected 1996 tests.
- `npm run test -- --help` confirmed Vitest runner availability.

Gaps by area:

| Area | Existing evidence | Gap |
| --- | --- | --- |
| Home/report history | Home tests and report normalizer tests exist | Shared report-quality utility moves need cross-route regression tests. |
| Admin logs/notifications | Backend API and frontend page tests exist | Shared notification/status display cleanup needs combined Admin Logs + Notifications tests. |
| Market freshness/provider fallback | Backend and frontend tests cover many provider states | Need measured hot-path timing under provider failure/cold-cache scenarios. |
| Scanner/watchlist workflows | Large `UserScannerPage` tests and backend scanner/watchlist tests exist | Need utility-level tests before moving scanner labels out of the page. |
| Backtest report | Backtest page/report tests exist | Native control warning cleanup needs browser checks and no formula changes. |
| Portfolio analytics | Portfolio page/service tests exist | Optimization must preserve accounting formulas and owner isolation. |
| DuckDB Phase 1/1.5/2 | Quant API/service tests exist and collect | Current dirty Phase 2 work should rerun disabled no-write and quant tests before commit. |
| Design guard | Guard passes with warnings | Warning burn-down should be tracked by count and affected files. |
| CI gate/preflight | Preflight works; ci_gate not run here | Full `ci_gate` should be run only by product-code sessions when dirty parallel work is interpretable. |
| Browser 390px checks | Not required for docs-only audit | Required for visible frontend cleanup. |

Markdown lint:

- No markdown lint script was found in the root or web package scripts by static search.

## 10. Prioritized optimization roadmap

### Phase 0. No-code cleanup and verification

| Task | Priority | Impact | Risk | Touched areas | Owner/session type | Recommended tests | Parallel? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Inventory ignored runtime artifacts and confirm ignore coverage | P2 | low | low | repo hygiene | docs/tooling audit | `git status --short`, `git ls-files --others --exclude-standard` | yes |
| Bundle composition report for current frontend build | P1 | medium | low | apps/dsa-web build | frontend tooling audit | `npm run build`, analyzer output if already available or locally added without commit | yes, read-only |
| Design guard warning inventory by file/rule | P1 | medium | low | apps/dsa-web | frontend audit | `npm run check:design` | yes |
| Docs audit index proposal | P3 | low | low | docs | docs audit | markdown inspection | yes |

### Phase 1. Low-risk consolidation

| Task | Priority | Impact | Risk | Touched areas | Owner/session type | Recommended tests | Parallel? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Extract scanner status/failure label helpers from `UserScannerPage.tsx` into a scanner utility | P1 | medium | medium | Scanner frontend | frontend implementation | `UserScannerPage.test.tsx`, `npm run lint`, `npm run build` | not with scanner UI work |
| Extract Admin Notifications status/tone helpers into a local utility or shared status adapter | P2 | medium | low | Admin notifications | frontend implementation | `AdminNotificationsPage.test.tsx`, `StatusBadge.test.tsx` | yes if no shared badge edit |
| Add utility tests around `DataFreshnessBadge` status labels before moving any market logic | P1 | medium | low | Market frontend | test-first frontend | `MarketOverviewPage.test.tsx`, new primitive tests | yes |

### Phase 2. Shared status/label utilities

| Task | Priority | Impact | Risk | Touched areas | Owner/session type | Recommended tests | Parallel? |
| --- | --- | --- | --- | --- | --- | --- |
| Define a display-status glossary that maps domain statuses into generic UI tones | P1 | high | medium | shared frontend UI/types | frontend architecture | `StatusBadge.test.tsx`, market/scanner/admin/backtest page tests | no, central touch |
| Add backend status vocabulary doc for API schema authors | P2 | medium | low | docs/API schema | docs/API audit | schema grep, docs review | yes |
| Remove duplicate page-local generic status mapping after tests are green | P2 | medium | medium | frontend pages | frontend implementation | targeted page tests, lint/build | no if shared utility is active |

### Phase 3. Performance profiling and memoization

| Task | Priority | Impact | Risk | Touched areas | Owner/session type | Recommended tests | Parallel? |
| --- | --- | --- | --- | --- | --- | --- |
| Profile Home, Scanner, Backtest result, Settings, and Market route renders | P1 | high | low | frontend | profiling/read-only | profiler notes, build output | yes |
| Memoize only measured expensive derived data | P2 | medium | medium | route-specific pages | frontend implementation | affected page tests and browser checks | yes by route |
| Lazy-load heavy report/chart/detail sections if bundle report supports it | P2 | medium | medium | report/backtest/home | frontend implementation | route tests, build, browser smoke | not with shared route refactors |

### Phase 4. Backend service/cache tightening

| Task | Priority | Impact | Risk | Touched areas | Owner/session type | Recommended tests | Parallel? |
| --- | --- | --- | --- | --- | --- | --- |
| Add timing instrumentation to market provider cold/fallback paths | P1 | high | medium | market backend | backend implementation | market cache/freshness tests, compile | not with market behavior changes |
| Verify scanner/watchlist/backtest caps and dedupe under batches | P1 | high | medium | scanner/watchlist/backtest backend/frontend | test-first backend/frontend | scanner/watchlist/backtest tests | split only by surface |
| Consolidate report/history decision-trace normalization behind tested adapters | P2 | medium | high | analysis/history/frontend | backend/frontend implementation | history, analysis, Home/report tests | no, cross-boundary |
| Keep DuckDB optional-service no-write guarantees before Phase 2 expansion | P0 for DuckDB work | high | medium | quant backend/docs/tests | backend implementation | quant API/service tests, disabled no-write smoke | no with active DuckDB session |

### Phase 5. Larger architecture changes after profiling

| Task | Priority | Impact | Risk | Touched areas | Owner/session type | Recommended tests | Parallel? |
| --- | --- | --- | --- | --- | --- | --- |
| Peel bounded repository paths out of `src/storage.py` | P2 | high | high | storage/repositories | backend architecture | focused DB tests, `ci_gate` | no |
| Split rule backtest/report services only around proven pain points | P3 | medium | high | backtest backend | backend architecture | full backtest tests | no |
| Decide admin notification ownership between Settings and `/admin/notifications` | P3 | medium | medium | admin frontend/docs | product/design + frontend | settings/admin tests, browser checks | no with settings redesign |

## 11. Safe parallelization matrix

Can run in parallel:

| Task A | Task B | Why |
| --- | --- | --- |
| Bundle composition report | Backend provider timing audit | Read-only and separate areas. |
| Design guard warning inventory | API schema vocabulary doc | Separate docs/frontend inspection. |
| Scanner label utility extraction | Portfolio backend profiling | Different files and product surfaces. |
| Admin notification helper extraction | Market primitive tests | Safe if neither edits shared `StatusBadge`. |
| Docs inventory | Any implementation task | Only if docs files are not shared/dirty. |

Should not run in parallel:

| Task A | Task B | Conflict |
| --- | --- | --- |
| Shared `StatusBadge` vocabulary change | Scanner/Admin/Backtest status refactors | Central utility affects all consumers. |
| Settings page decomposition | Notification channel Settings/Admin ownership work | Same IA and files. |
| Market freshness helper consolidation | Market backend provider/fallback behavior changes | Contract and behavior can drift together. |
| DuckDB Phase 2 implementation | Any quant docs/tests cleanup | Current dirty quant files are already an active area. |
| Storage repository extraction | Auth/history/portfolio persistence changes | High risk of hidden coupling. |
| Backtest report lazy loading | Backtest calculation/service changes | Harder to separate UI regressions from domain regressions. |

## 12. Appendix

### Preflight summary

- `pwd`: `/Users/yehengli/daily_stock_analysis`
- Branch: `main`
- Upstream: `origin/main` ahead 0, behind 0
- Dirty files before audit: 8, all pre-existing and not touched by this audit.
- Dirty categories: docs 3, api 2, tests 2, src 1.
- Recent commits include the requested DuckDB, Home, Backtest, Admin, Portfolio, Watchlist, Market, Settings, Scanner, CI, and UI commits. `d077d66`, `cb8abcf`, and `0059751` are present; active uncommitted quant files suggest DuckDB Phase 2 may still be in progress.

Pre-existing dirty files:

```text
api/v1/endpoints/quant.py
api/v1/schemas/quant.py
docs/CHANGELOG.md
docs/operations/duckdb-operator-smoke-guide.md
docs/quant-duckdb-engine.md
src/services/quant_analytics/duckdb_service.py
tests/api/test_quant_duckdb.py
tests/test_quant_duckdb_service.py
```

### Repository hygiene summary

- Tracked files: 1006.
- Unignored untracked files: none.
- Ignored/local cache directories found: `.pytest_cache`, multiple `__pycache__` directories, including under `tests`, `api`, `bot`, `data_provider`, `src`, `scripts`, `patch`, and `.venv`.
- Local runtime artifacts found: `logs/api_server_20260504.log`, `logs/api_server_20260505.log`, `logs/api_server_debug_20260505.log`, `logs/api_server_debug_20260504.log`, `data/stock_analysis.db`.
- No `.duckdb` or `.duckdb.wal` files were found by the max-depth artifact search.

### Frontend check summary

- `npm run check:design`: passed with 103 warnings across 213 scanned files.
- `npm run lint`: passed.
- `npm run build`: passed; Vite emitted a large chunk warning.
- Frontend TS/TSX files under `src`: 282.
- Largest frontend TSX files: `SettingsPage.tsx` 5,007 lines, `UserScannerPage.tsx` 4,553, `HomeBentoDashboardPage.tsx` 3,929, `PortfolioPage.tsx` 2,925, `MarketOverviewPage.tsx` 2,472.
- Vitest CLI is available through `npm run test -- --help`.

### Backend check summary

- `python3 -m compileall -q src api`: passed.
- `python3 -m pytest --collect-only -q`: collected 1996 tests.
- Python test files: 168.
- Largest backend/API files: `rule_backtest_service.py` 9,370 lines, `storage.py` 7,038, `market_scanner_service.py` 5,696, `pipeline.py` 4,574, `portfolio_service.py` 4,515.

### Audit classification key

- Confirmed issue: directly evidenced by command output or static source inspection.
- Likely issue needing verification: static evidence suggests risk, but runtime/profile/build-detail evidence is not enough.
- Intentional duplication / acceptable redundancy: duplicate-looking code appears to preserve domain semantics or route/product boundaries.
- Risky optimization that should wait: valid optimization idea with high regression risk or insufficient profiling.
- No-action-needed observation: inspected item does not need a task now.
