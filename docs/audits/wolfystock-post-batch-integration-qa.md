# WolfyStock Post-Batch Integration QA

Status: Superseded
Owner domain: Launch readiness QA
Replacement or related docs: `docs/audits/public-launch-gap-register.md`, `docs/audits/final-pre-push-audit.md`

Date: 2026-05-06
Mode: QA/reporting. No runtime behavior changes intended.

## 1. Scope

Verified recent main-branch work as a lightweight integration pass:

- `6f634faf feat(admin): add market provider operations dashboard`
- `dfb3b079 fix(admin): polish market provider operations dashboard`
- `c68af295 test(market): cover overview request staging`
- `69356203 test(scanner): cover initial runs fetch dedupe`
- `5423e81e fix(ui): localize remaining chinese route labels`
- `601d770c docs: audit llm and external api cost risks`
- `a6ab3fa0 docs: design duplicate-cost metrics`

Static commit-scope check found the dashboard commits only touched frontend route, API client, navigation/i18n, and tests. No backend provider runtime files were changed by the dashboard polish commit.

## 2. Git and Artifact Hygiene

- Required preflight passed: `pwd` was `/Users/yehengli/daily_stock_analysis`; branch was `main`.
- Upstream status from `./scripts/task_preflight.sh`: `origin/main` ahead 0 / behind 0.
- Initial dirty state: untracked `apps/dsa-web/playwright-artifacts/`.
- `apps/dsa-web/src/pages/ChatPage.tsx` and `apps/dsa-web/src/pages/__tests__/ChatPage.test.tsx` were not dirty in this run and were not touched.
- Inspected `apps/dsa-web/playwright-artifacts/`; it contained only generated PNG screenshots:
  - `apps/dsa-web/playwright-artifacts/market-provider-operations/desktop-1440x1000.png`
  - `apps/dsa-web/playwright-artifacts/market-provider-operations/mobile-390x844.png`
- Removed only that untracked generated artifacts directory. No broad `git clean` was used.
- Before creating this report, `git status --short` was clean.

## 3. Verification Summary

| Area | Check | Result | Evidence |
| --- | --- | --- | --- |
| Market Provider Operations dashboard | `/zh/admin/market-providers` route exists and is admin-only | PASS | `App.tsx` wraps `/admin/market-providers` and localized route with `AdminSurfaceRoute`; `AppRoutes.test.tsx` covers admin access. |
| Market Provider Operations dashboard | Consumes only `GET /api/v1/admin/market-providers/operations` | PASS | `marketProviderOperationsApi.getOperations()` uses that endpoint; browser QA saw only that dashboard API call. |
| Market Provider Operations dashboard | Dashboard remains read-only | PASS | UI shows `只读`, `外部调用关闭`, `缓存不变更`; page copy says it does not trigger provider calls, mutate cache, or change provider order. |
| Market Provider Operations dashboard | Raw endpoint paths/reason codes/API internals collapsed by default | PASS | Test asserts raw endpoint and `fallback_used` are not visible; browser QA confirmed `/api/v1/market/market-briefing` hidden by default. |
| Market Overview request staging regression | 10 immediate, 3 at 250 ms, 4 at 650 ms, all 17 once, StrictMode stream dedupe | PASS | `MarketOverviewPage.test.tsx` has explicit `countMarketPanelRequests()` expectations and `MockEventSource.instances` length checks. |
| Scanner initial request dedupe regression | Desktop-like and narrow `/zh/scanner` initial `getRuns` once | PASS | `UserScannerPage.test.tsx` covers viewport widths `1280` and `390`, each with `getRuns` once. |
| Backtest Chinese labels | `/zh/backtest` Chinese chrome/accessibility labels intact | PASS | `BacktestPage.test.tsx` and browser QA confirmed Chinese labels such as `确定性回测`, `策略模板`, and `执行回测任务`. |
| Backtest Chinese labels | Intentional English limited to domain tokens | PASS | Browser QA found only expected domain tokens on `/zh/backtest`: `MACD`, `SMA`, `EMA`, `RSI`, `BP`, `QQQ`, `SPY`. |
| LLM/provider cost audit docs | Next path is instrumentation-only counters, read-only summary, then cache prototypes | PASS | Both audit docs state instrumentation first, duplicate-cost admin summary second, and cache/design prototypes only after measurement. |
| Duplicate-cost metrics design docs | Explicitly avoids runtime/cache/provider/AI decision changes | PASS | Guardrails preserve provider order/fallback, MarketCache TTL/SWR/cold-start, scanner ranking, prompts, routing, notification, portfolio, backtest, and DuckDB runtime. |

## 4. Tests/Checks Run

| Command | Result |
| --- | --- |
| `cd apps/dsa-web && npm run test -- src/pages/__tests__/MarketProviderOperationsPage.test.tsx` | PASS: 1 file, 4 tests |
| `cd apps/dsa-web && npm run test -- src/pages/__tests__/MarketOverviewPage.test.tsx` | PASS: 1 file, 60 tests |
| `cd apps/dsa-web && npm run test -- src/pages/__tests__/UserScannerPage.test.tsx` | PASS: 1 file, 59 tests |
| `cd apps/dsa-web && npm run test -- src/pages/__tests__/BacktestPage.test.tsx` | PASS: 1 file, 26 tests |
| `cd apps/dsa-web && npm run test -- src/__tests__/AppRoutes.test.tsx` | PASS: 1 file, 26 tests |
| `cd apps/dsa-web && npm run check:design` | PASS: 219 files scanned; no blocking violations or warnings |
| `cd apps/dsa-web && npm run lint` | PASS |
| `cd apps/dsa-web && npm run build` | PASS with existing Vite large chunk warning for `DeterministicBacktestChartWorkspace` |
| `./scripts/ci_gate.sh` | PASS: `2002 passed, 3 skipped, 1 warning, 203 subtests`; local warnings: `flake8` and `akshare` not installed |

## 5. Browser/Playwright Verification

Method:

- Existing frontend listener reused: `http://127.0.0.1:5173`.
- Existing backend listener on `127.0.0.1:8000` was observed only; not restarted or killed.
- No temporary repo-local dev server was started.
- Auth and API responses were mocked in Playwright.
- No external market providers or real LLM APIs were called.

Ports inspected before browser verification:

| Port | Status at inspection | Use |
| --- | --- | --- |
| `8000` | Existing Python backend listener | Observed only |
| `8001` | No listener seen | Not used |
| `5173` | Existing node/Vite listener | Reused for browser QA |
| `4173` | No listener seen | Not used |
| `5174` | No listener seen | Not used |
| `5175` | No listener seen | Not used |
| `5176` | No listener seen | Not used |

| Route | Viewport | Result | Observations | Screenshot |
| --- | --- | --- | --- | --- |
| `/zh/admin/market-providers` | `1440x1000` | PASS | No console/page errors; no horizontal overflow; read-only badges visible; developer details collapsed; only operations endpoint called. | `/tmp/wolfystock-post-batch-qa/zh_admin_market-providers-desktop-1440x1000.png` |
| `/zh/admin/market-providers` | `390x844` | PASS | No console/page errors; no horizontal overflow; read-only state visible; developer details collapsed; only operations endpoint called. | `/tmp/wolfystock-post-batch-qa/zh_admin_market-providers-mobile-390x844.png` |
| `/zh/backtest` | `1440x1000` | PASS | No console/page errors; no horizontal overflow; Chinese chrome visible; old English labels absent; only mocked backtest APIs called. | `/tmp/wolfystock-post-batch-qa/zh_backtest-desktop-1440x1000.png` |
| `/zh/backtest` | `390x844` | PASS | No console/page errors; no horizontal overflow; Chinese chrome visible; old English labels absent; only mocked backtest APIs called. | `/tmp/wolfystock-post-batch-qa/zh_backtest-mobile-390x844.png` |

## 6. Behavior Unchanged Confirmation

This QA pass created only this report document. It did not change:

- provider runtime, provider order, fallback behavior, freshness semantics, or MarketCache TTL/SWR/cold-start behavior
- scanner scoring, ranking, thresholds, profiles, universe, candidate logic, or CSV headers
- backtest calculations, accounting, or chart data semantics
- portfolio accounting, P&L, exposure, FX, concentration, holdings, or cash semantics
- AI decision logic, LLM routing, prompt logic, or notification routing
- DuckDB production runtime
- dependencies, package files, or broad formatting

## 7. Follow-Up Recommendations

1. Instrumentation-only backend counters for LLM/provider seams.
2. Read-only duplicate-cost admin summary after counters exist.
3. Market Overview cache hit/stale/miss reporting.
4. Guest preview reuse design only after measurement.
