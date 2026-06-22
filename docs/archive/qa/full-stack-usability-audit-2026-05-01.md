# WolfyStock Full-Stack Usability, UX, and Observability Audit - 2026-05-01

## 1. Executive Summary

Overall platform health: **Partial / not release-ready for observability-sensitive workflows**.

The core application can boot locally after refreshing frontend dependencies, protected APIs correctly reject unauthenticated requests, and many existing backend/frontend tests pass. However, the audit found a **high-severity observability gap in guest analysis**, a **market overview fallback regression**, broad **missing actor attribution** across scanner/market logs, and **portfolio write operations that are not represented in execution logs**.

Most severe defects:

| Rank | Defect |
| --- | --- |
| 1 | Guest ORCL analysis preview timed out after 130s and created no new ORCL execution log session. |
| 2 | Guest preview endpoint uses `persist_history=False` and does not call `ExecutionLogService`, so guest activity cannot reliably appear in Admin Logs. |
| 3 | Scanner and Market Overview logs are persisted without user/guest actor attribution. |
| 4 | Portfolio trade/cash/corporate-action write endpoints have validation and ownership checks, but no execution-log/audit record. |
| 5 | Market Overview fallback test fails: when one initial API request fails, the expected "情绪与资金面" card/heading is absent. |

Top UX blockers:

- Guest ORCL analysis did not visibly enter/complete a loading/result state in the in-app browser.
- Several protected routes either show a sign-in gate plus a lingering boot-status overlay, or silently redirect to `/guest`, which makes access state inconsistent.
- Admin Logs could not be manually verified in UI because no admin password/session was available after logout; API returned `401 Login required`.

Top backend/API risks:

- `/api/v1/analysis/preview` is synchronous, unauthenticated, long-running, and not logged on start/failure/timeout.
- Admin Logs root business-event search is strong for `business_event` sessions, but Market Overview uses `market_overview`/`log` summary keys rather than `business_event`, making root-level Admin Logs searchability inconsistent.
- API contracts are generally present, but authenticated-only endpoints all redirect/401 for unauthenticated users, limiting guest test coverage to the home preview path.

## 2. Test Environment

| Item | Value |
| --- | --- |
| Repo | `/Users/yehengli/daily_stock_analysis` |
| Branch | `main` |
| Commit | `dc5cafe2f14c7fb6c08b1965b9a2c705d428948c` |
| Frontend URL used | `http://127.0.0.1:5173` |
| Backend URL used | `http://127.0.0.1:8000` |
| Browser/tool | Codex in-app browser (`browser-use` iab backend), curl, sqlite3, pytest, Vitest |
| Auth mode | Backend auth enabled; unauthenticated curl; in-app browser initially had a session, then guest/locked route checks were run without a usable admin password. |
| Existing dirty files before audit | `api/v1/schemas/system_config.py`, `apps/dsa-web/src/i18n/core.ts`, `apps/dsa-web/src/pages/SettingsPage.tsx`, `apps/dsa-web/src/pages/__tests__/SettingsPage.test.tsx`, `apps/dsa-web/src/types/systemConfig.ts`, `docs/CHANGELOG.md`, `src/core/config_registry.py`, `src/services/system_config_service.py`, `tests/test_system_config_api.py`, `tests/test_system_config_service.py` |
| Environment repair | `npm ci` in `apps/dsa-web` repaired a broken Vite dependency tree. It changed `node_modules` only and reported 10 npm audit vulnerabilities. |

Initial commands:

```bash
git status --short
git branch --show-current
git log --oneline -5
```

Initial state:

```text
main
dc5cafe2 refactor(scanner): expose scan diagnostics and result table
f3eb6271 fix(market-overview): repair selector visibility and compact quote rows
d365a0be refactor(market-overview): align shell width with home
8c36640d fix(settings): clean input padding and button styling
f7600c18 refactor(market-overview): rebuild full-width dashboard layout
```

## 3. Workflow Results

### A. Guest mode / unauthenticated analysis

Steps performed:

1. Opened `/guest` in the in-app browser.
2. Entered `ORCL` into the guest analysis input.
3. Clicked `Analyze`.
4. Cross-checked with direct public API call:

```bash
curl -sS -D - -X POST http://127.0.0.1:8000/api/v1/analysis/preview \
  -H 'Content-Type: application/json' \
  -d '{"stock_code":"ORCL","report_type":"brief","force_refresh":true}' \
  --max-time 130
```

Expected:

- Guest analysis should show a loading state, return a preview or a friendly timeout/failure state, and create an execution/audit log with guest/session attribution.

Actual:

- Browser click left the guest form on the same visible state; no stable `Analyzing...` or result state was observed.
- Direct API call timed out after 130 seconds with no response body.
- ORCL execution-log session count was **12 before and 12 after** the public preview call.
- No `analysis_history` row with `query_id LIKE 'guest:%'` was found in SQLite, consistent with `persist_history=False`.

Related code/endpoints:

- `POST /api/v1/analysis/preview`
- `api/v1/endpoints/analysis.py:170`
- `api/v1/endpoints/analysis.py:184`
- `api/v1/endpoints/analysis.py:190`
- `api/v1/endpoints/analysis.py:222`

Result: **Fail**

Severity: **High**

### B. Authenticated analysis

Steps performed:

1. Static inspection of authenticated sync analysis path.
2. SQLite inspection of existing ORCL execution-log sessions.

Expected:

- Authenticated analysis should create Admin Logs entries with symbol, status, request/query id, execution steps, and authenticated actor when available.

Actual:

- Existing ORCL execution-log sessions exist for authenticated or task-queue analysis.
- The sync analysis path explicitly calls `ExecutionLogService.start_analysis_execution(...)`.
- Actor/user attribution is only populated when `owner_id` is available; existing sampled sessions often had blank `actor_user` / `business_user`.

Evidence:

```sql
SELECT COUNT(*) AS orcl_session_count
FROM execution_log_sessions
WHERE code='ORCL' OR summary_json LIKE '%ORCL%';
-- 12
```

Related code/endpoints:

- `api/v1/endpoints/analysis.py:451`
- `api/v1/endpoints/analysis.py:464`
- `src/services/execution_log_service.py:812`
- `src/services/execution_log_service.py:816`

Result: **Partial**

Severity: **Medium**

### C. Home decision panel / stock analysis

Steps performed:

1. Opened `/` and `/guest`.
2. Confirmed guest landing renders the WolfyStock command center and ticker input.
3. Tested ORCL guest path as above.

Expected:

- Home should handle both guest and authenticated states consistently, with visible loading/result/error states.

Actual:

- Guest landing renders.
- Guest analysis did not visibly progress in browser and timed out by API.
- Home was the only meaningful unauthenticated analysis surface available without credentials.

Result: **Partial**

Severity: **High** because this is the entry workflow for unauthenticated users.

### D. Chat / question page

Steps performed:

1. Opened `/chat` unauthenticated in the browser.
2. Inspected chat endpoint and existing execution log rows.

Expected:

- Guest should be blocked clearly; authenticated chat should log request, actor, stock symbol when present, tools, and failure/success.

Actual:

- `/chat` shows a sign-in gate: "Sign in to unlock Ask Stock".
- `POST /api/v1/agent/chat` requires `get_current_user`.
- Existing agent chat log for ORCL exists but failed, with `user_id=bootstrap-admin` in tool events and no robust guest case.

Related code/endpoints:

- `POST /api/v1/agent/chat`
- `api/v1/endpoints/agent.py:186`
- `api/v1/endpoints/agent.py:209`

Result: **Partial**

Severity: **Medium**

### E. Scanner

Steps performed:

1. Opened `/scanner` unauthenticated in the browser.
2. Inspected scanner observability storage.
3. Queried latest scanner execution-log summaries.

Expected:

- Guest should be blocked or redirected consistently.
- Scanner runs should log market, profile, selected/scanned counts, actor/user/session id.

Actual:

- Browser showed "Sign in to unlock Market Scanner" plus a lingering boot-status overlay.
- Scanner logs include market/profile/shortlist coverage.
- Actor fields are blank: latest scanner rows show `actor_user` and `business_user` empty.

Evidence:

```sql
SELECT json_extract(summary_json,'$.scanner_run.market') AS market,
       json_extract(summary_json,'$.scanner_run.profile') AS profile,
       json_extract(summary_json,'$.scanner_run.shortlist_count') AS shortlist_count,
       json_extract(summary_json,'$.meta.actor.user_id') AS actor_user
FROM execution_log_sessions
WHERE summary_json LIKE '%scanner_run%'
ORDER BY id DESC LIMIT 3;
-- us | us_preopen_v1 | 5 | NULL/blank
```

Related code/endpoints:

- `src/services/market_scanner_ops_service.py:243`
- `src/services/execution_log_service.py:1195`
- `src/services/execution_log_service.py:1234`
- `src/services/execution_log_service.py:1271`

Result: **Partial**

Severity: **Medium**

### F. Portfolio

Steps performed:

1. Opened `/portfolio` unauthenticated.
2. Inspected portfolio write endpoints and service methods.
3. Did not create, delete, or mutate portfolio data.

Expected:

- Guest should not see account-specific data.
- Authenticated portfolio writes should be audit/loggable with actor, account, event id, symbol/currency, and validation result.

Actual:

- Browser shows sign-in gate for Portfolio.
- API returns `401 Login required` unauthenticated.
- Portfolio write endpoints call `PortfolioService.record_trade`, `record_cash_ledger`, and `record_corporate_action` but do not call `ExecutionLogService`.

Related code/endpoints:

- `POST /api/v1/portfolio/trades`
- `POST /api/v1/portfolio/cash-ledger`
- `api/v1/endpoints/portfolio.py:381`
- `api/v1/endpoints/portfolio.py:493`
- `src/services/portfolio_service.py:525`

Result: **Partial**

Severity: **Medium**

### G. Market Overview

Steps performed:

1. Opened `/market-overview` unauthenticated.
2. Ran `MarketOverviewPage.test.tsx`.
3. Inspected market overview observability storage.

Expected:

- Guest should be blocked clearly.
- Authenticated Market Overview should show all tabs/cards and fallback states; failures should not hide unrelated cards.
- Market logs should be searchable and attributable.

Actual:

- Browser shows sign-in gate for Premium module.
- `MarketOverviewPage.test.tsx` failed one test: `keeps other cards visible when one initial API request fails`.
- Latest execution logs are dominated by `market_overview_fetch` sessions; many have no `business_event` summary and blank actor fields.

Related code/endpoints:

- `src/services/market_overview_service.py:527`
- `src/services/market_overview_service.py:570`
- `src/services/market_overview_service.py:609`
- `src/services/execution_log_service.py:1337`
- `src/services/execution_log_service.py:1398`

Result: **Fail**

Severity: **High** for fallback UX regression; **Medium** for observability structure.

### H. Backtest

Steps performed:

1. Opened `/backtest` unauthenticated.
2. Ran focused backend and frontend backtest tests.

Expected:

- Guest should be blocked.
- Authenticated backtest should validate forms, run small jobs safely, and log actor/request/run id.

Actual:

- Browser shows sign-in gate for Backtest.
- Focused backend backtest suite passed: `201 passed, 1 warning`.
- Frontend `BacktestPage.test.tsx` passed: `23 passed`.
- Live authenticated form interactions were not run because no admin credentials were available.

Result: **Partial**

Severity: **Low/Medium**

### I. Settings / System Settings

Steps performed:

1. Opened `/settings` and `/settings/system` unauthenticated.
2. Ran focused Settings tests and inspected auth behavior.
3. Did not save config or open dangerous actions.

Expected:

- Guest should be blocked clearly.
- Authenticated Settings should keep secrets masked, preserve masked placeholders, and require confirmation for dangerous actions.

Actual:

- `/settings` and `/settings/system` redirected to `/guest` rather than showing the same sign-in gate pattern used by Portfolio/Backtest/Chat.
- Focused Settings tests passed: `64 passed`.
- API `/api/v1/system/config` returned `401 Login required` unauthenticated.
- Existing dirty Settings files were present before this audit; this audit did not modify them.

Result: **Partial**

Severity: **Medium** for inconsistent access UX; security masking not fully UI-verified due auth blocker.

### J. Admin Logs / Execution Trace

Steps performed:

1. Requested Admin Logs API unauthenticated.
2. Inspected SQLite `execution_log_sessions` and `execution_log_events`.
3. Inspected admin log query/filter implementation.

Expected:

- Admin Logs should require admin auth.
- Search/filter should find analysis, scanner, backtest, market, settings/security events with actor/request/symbol where applicable.

Actual:

- API returned `401 Login required`.
- Existing ORCL analysis logs are present.
- Fresh guest ORCL preview created no new log.
- Scanner logs are searchable in sessions, but lack actor.
- Market Overview logs persist as market/log summaries, not business events, so root Admin Logs business-event search may not include them consistently.
- Some log categories are very noisy: thousands of market-related rows exist locally.

Result: **Partial**

Severity: **High** for guest observability gap; **Medium** for actor/search consistency.

## 4. Defect Table

| ID | Severity | Area | Title | Reproduction steps | Expected | Actual | Likely root cause | Suggested fix | Surface | Needs new test? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| QA-001 | High | Guest Analysis / Observability | Guest ORCL preview is not logged | Open `/guest`, analyze ORCL, or call `POST /api/v1/analysis/preview` with ORCL; inspect `execution_log_sessions` | Log exists with guest/session actor and ORCL | API timed out after 130s; ORCL log count unchanged | Preview path does not call `ExecutionLogService`; no start/fail timeout log | Add guest-aware execution log lifecycle around preview, including timeout/failure; include guest session id | Backend + frontend | yes |
| QA-002 | High | Guest Analysis / UX | Guest ORCL analyze click has no stable visible progress/result | Browser `/guest`, fill ORCL, click Analyze | Button/loading/result/error should update | Snapshot remained on form; no stable `Analyzing...` or result observed | Long synchronous API call and weak UI progress/error handling | Add deterministic loading state, timeout messaging, and retry affordance | Frontend + backend | yes |
| QA-003 | Medium | Admin Logs / Actor Attribution | Scanner logs lack actor/user attribution | Inspect latest scanner `summary_json` | `userId` or guest/session actor present | `actor_user` and `business_user` blank | `record_scanner_run` defaults actor to `None`; ops service does not pass user | Pass current user/trigger actor into scanner ops and log service | Backend | yes |
| QA-004 | Medium | Admin Logs / Searchability | Market Overview logs are not business events | Trigger/open market overview; inspect latest `market_overview_fetch` rows | Admin Logs root business-event search can find market refresh events | Rows use `market_overview`/`log` summaries, not `business_event` | `record_market_overview_fetch` writes a different summary shape | Either expose market log search in UI explicitly or mirror essential fields into business_event | Backend + frontend | yes |
| QA-005 | High | Market Overview / Resilience | One initial card failure hides expected card heading | Run `npm run test -- src/pages/__tests__/MarketOverviewPage.test.tsx` | Other cards remain visible | Test failed: cannot find heading `/情绪与资金面/i` | Recent layout/fallback change likely removed/renamed expected resilient card section | Restore resilient card rendering or update contract deliberately with new test expectations | Frontend | yes |
| QA-006 | Medium | Portfolio / Audit | Portfolio writes have no execution-log audit | Inspect `POST /portfolio/trades`, `cash-ledger`, `corporate-actions` paths | Writes logged with actor/account/symbol/currency/status | Service writes data but does not call execution log service | No portfolio audit instrumentation | Add `record_portfolio_event` style log for create/delete/import/sync outcomes | Backend | yes |
| QA-007 | Medium | Access UX | Protected route behavior is inconsistent | Open `/chat`, `/portfolio`, `/market-overview`, `/backtest`, `/settings`, `/admin/logs` unauthenticated | Consistent sign-in gate or redirect pattern | Some pages show sign-in gate; settings/admin redirect to `/guest`; scanner gate leaves boot overlay | Route guard / surface-role handling differs by route | Normalize protected route handling and remove stale boot overlay after gate renders | Frontend | yes |
| QA-008 | Low | Tooling / Dev UX | Running Vite server initially returned internal 500 | `curl http://127.0.0.1:5173/` before `npm ci` | App shell loads | Vite error: missing `vite/dist/node/chunks/dist.js` | Broken/stale `node_modules` | `npm ci`; consider dev setup check | Environment | no |
| QA-009 | Medium | Security / Dependencies | Frontend dependency audit reports vulnerabilities | Run `npm ci` | No high vulnerabilities | `10 vulnerabilities (4 moderate, 6 high)` | Current dependency tree | Triage `npm audit` output in a separate security task | Frontend | yes |

## 5. Observability Matrix

| Workflow | Log? | Where recorded | Searchable in Admin Logs? | Actor attribution? | Symbol/request id? | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Guest analysis -> ORCL | No for fresh test | None observed in `execution_log_sessions`; no `analysis_history` guest row | No | No | No | `POST /analysis/preview` timed out; code uses guest query id but no log service. |
| Admin/auth analysis | Yes / partial | `execution_log_sessions`, `execution_log_events` | Yes for sessions/business events | Partial | Yes | Existing ORCL logs found; actor blank in sampled rows unless owner id is passed. |
| Chat question | Partial | Agent chat/tool execution logs | Partial | Yes for sampled bootstrap-admin tool events | Partial | Guest blocked. Existing ORCL chat log failed due LLM error; request message is logged and should be sanitized. |
| Scanner run | Yes / partial | `execution_log_sessions` with `scanner_run` summary | Yes in sessions; root depends on business_event | No | scanner id yes; symbol no | Market/profile/shortlist count present, actor blank. |
| Backtest run | Partial | Existing execution service supports backtest; focused tests passed | Needs live admin confirmation | Needs confirmation | run id likely | Live run not performed due missing admin credentials. |
| Portfolio transaction | No confirmed execution log | Portfolio tables only | No | No execution-log actor | Event id only in portfolio table | Static inspection found no log call on create/write paths. |
| Settings change | Yes for admin actions | `ExecutionLogService.record_admin_action` in system config service | Yes | Expected admin actor | action id/target | Save not performed. Existing tests passed. |
| Market overview refresh | Yes / partial | `execution_log_sessions` task_id=`market_overview_fetch` | Sessions yes; root business-event search inconsistent | No in sampled rows | log session id, endpoint | High volume; many rows lack `business_event` shape. |

## 6. Guest vs Authenticated Logging Finding

Special ORCL finding: **reproduced as missing guest observability**.

What was verified:

- Before test, SQLite contained 12 ORCL-related execution-log sessions from earlier authenticated/task runs.
- Fresh `POST /api/v1/analysis/preview` for ORCL timed out after 130 seconds.
- After test, ORCL-related execution-log session count remained 12.
- `analysis_history` had no `query_id LIKE 'guest:%'` row.
- Static inspection confirms `preview_analysis()` creates a `guest:<session>:<timestamp>` query id and calls `AnalysisService.analyze_stock(..., persist_history=False)` but does **not** call `ExecutionLogService`.
- Authenticated sync analysis path does call `ExecutionLogService.start_analysis_execution(...)`.

Classification:

- Missing log record: **yes, for fresh guest ORCL preview**.
- Log exists but not shown in UI: **not supported by evidence**.
- Log exists but cannot be searched: **not for the fresh guest preview; no log was found**.
- Log exists but lacks actor: **applicable to scanner/market and some existing analysis rows, but not the fresh guest preview because no log exists**.
- Endpoint not instrumented: **yes**.
- Missing feature: **guest/anonymous/session actor attribution in execution logs**.

## 7. UX/Layout Findings

### Guest/Home

- Guest landing renders a clean command center with ticker input.
- ORCL analysis click did not produce a stable visible loading/result state in browser.
- Direct API timed out, so UI should expose timeout/failure rather than leaving the user uncertain.

### Chat

- Guest state is clear: "Sign in to unlock Ask Stock".
- Live prompt validation was not run because auth was unavailable.

### Scanner

- Guest state shows "Sign in to unlock Market Scanner".
- A boot-status overlay remains in the DOM with the gate, which may be confusing/noisy for assistive tech and screenshots.

### Portfolio

- Guest state is correctly protected and does not expose account-specific data.
- Form validation could not be manually exercised without auth; backend tests cover many portfolio validation/ownership cases.

### Market Overview

- Guest state shows sign-in gate.
- Frontend regression test shows card resilience failure when one initial API request fails.
- Market logs are noisy and likely hard for admins to separate from actionable user activity.

### Backtest

- Guest state is correctly protected.
- Focused backend and frontend tests passed; live dropdown/clipping checks were not possible without auth.

### Settings

- `/settings` and `/settings/system` redirect to `/guest` instead of showing the sign-in gate pattern used by several other protected routes.
- Secret masking was not browser-verified because no admin session was available. Existing focused tests passed.

### Admin Logs

- `/admin/logs` redirects to `/guest` unauthenticated.
- Admin API returns `401 Login required`.
- Populated DB inspection shows logs exist, but actor attribution coverage is weak.

## 8. Backend/API Findings

- `POST /api/v1/analysis/preview` can exceed 130 seconds with no response and no execution log.
- All sampled protected APIs correctly returned `401 Login required` unauthenticated:
  - `/api/v1/admin/logs/sessions?limit=5`
  - `/api/v1/market/overview`
  - `/api/v1/scanner/recent-runs?limit=3`
  - `/api/v1/backtest/runs?limit=3`
  - `/api/v1/portfolio/summary`
  - `/api/v1/system/config`
- Some sampled URL guesses were invalid for current backend route names, because frontend uses `/api/v1/market-overview/*`, `/api/v1/scanner/runs`, and `/api/v1/portfolio/snapshot` rather than the guessed variants. This is not a product defect, but it shows why contract tests should use the frontend API client map.
- Market Overview logs are written for stale/fallback cases but not shaped like business events.
- Portfolio writes are authenticated/owner-scoped but not execution-log instrumented.
- Agent chat logs exist through lower-level agent/tool observability, but the endpoint itself does not create an explicit request lifecycle log.

## 9. Security/Safety Findings

- No raw secrets, tokens, cookies, or API keys were copied into this report.
- Existing secret sanitization tests passed:
  - `tests/api/test_admin_logs.py`
  - `tests/test_execution_log_service.py`
  - `tests/api/test_system_config.py`
- System config API is protected by auth; unauthenticated request returned `401`.
- Dangerous settings actions were not executed.
- `npm ci` reported 6 high and 4 moderate vulnerabilities; this needs a separate dependency-security review.
- Browser logs collected during route smoke did not show console errors.

## 10. Recommended Fix Roadmap

### Phase 1: Critical observability/auth/security fixes

1. Instrument `POST /api/v1/analysis/preview` with execution-log lifecycle:
   - start log immediately before analysis
   - finish success/failure/timeout
   - include `actor.kind=guest`, `guestSessionId`, `requestId/queryId`, symbol, route
2. Add guest timeout handling and a frontend-visible retry/error state.
3. Add actor propagation to scanner and market overview observability.
4. Triage npm audit high vulnerabilities.

### Phase 2: High-impact UX blockers

1. Fix Market Overview fallback rendering so unaffected cards remain visible.
2. Normalize protected route behavior: sign-in gate vs redirect should be deliberate and consistent.
3. Remove lingering boot-status overlay from gated/protected states once content is ready.

### Phase 3: Contract/tests hardening

1. Add guest ORCL preview observability tests.
2. Add Admin Logs search tests for guest/session actor, scanner actor, and market overview business search.
3. Add portfolio audit-log tests for trade/cash/corporate-action create/delete/import/sync.
4. Add endpoint-map contract tests from frontend API client routes to backend registered routes.

### Phase 4: Polish and performance

1. Split large frontend chunks flagged by Vite if load performance matters.
2. Reduce market-log noise and improve default Admin Logs grouping.
3. Add responsive browser checks for mobile/laptop/desktop once admin credentials are available.

## 11. Tests to Add

| Finding | Backend tests | Frontend tests |
| --- | --- | --- |
| Guest preview not logged | `tests/api/test_guest_analysis_observability.py::test_guest_preview_records_execution_log_with_guest_actor`; timeout/failure variant | Guest Home test asserting loading, timeout error, retry, and log correlation id display if exposed |
| Missing actor attribution | Scanner/market service tests asserting `summary_json.meta.actor` and `business_event.userId` or guest id | AdminLogsPage test showing Actor column for scanner/market rows |
| Market Overview fallback regression | API fallback contract already exists; add route-level regression if needed | Fix existing `MarketOverviewPage.test.tsx::keeps other cards visible when one initial API request fails` |
| Portfolio audit gap | Tests for trade/cash/corporate-action create/delete logging with owner id | AdminLogsPage fixture row for portfolio event search/filter |
| Access UX inconsistency | Route guard unit tests for settings/admin protected behavior | Browser or Vitest route tests for `/settings`, `/settings/system`, `/admin/logs` unauthenticated behavior |
| API route/client contract | Backend route registry vs frontend API client route map test | Frontend API client smoke with mocked 401/200 shapes |

## 12. Appendix

### Commands run

```bash
git status --short
git branch --show-current
git log --oneline -5
git rev-parse HEAD
git diff --stat
lsof -nP -iTCP:5173 -sTCP:LISTEN
lsof -nP -iTCP:8000 -sTCP:LISTEN
curl -sS -D - http://127.0.0.1:8000/api/v1/auth/status
curl -sS -D - http://127.0.0.1:5173/
npm ci
curl -sS -D - -X POST http://127.0.0.1:8000/api/v1/analysis/preview -H 'Content-Type: application/json' -d '{"stock_code":"ORCL","report_type":"brief","force_refresh":true}' --max-time 130
sqlite3 data/stock_analysis.db ".tables"
sqlite3 data/stock_analysis.db "PRAGMA table_info(execution_log_sessions); PRAGMA table_info(execution_log_events);"
sqlite3 data/stock_analysis.db "<sanitized ORCL/log queries>"
python3 -m py_compile api/v1/endpoints/*.py src/services/*.py src/core/*.py
python3 -m pytest tests/api/test_admin_logs.py -q
python3 -m pytest tests/api/test_system_config.py -q
python3 -m pytest tests/test_execution_log_service.py -q
python3 -m pytest tests/test_market_scanner_service.py -q
python3 -m pytest tests/test_*backtest*.py -q
npm run test -- src/pages/__tests__/AdminLogsPage.test.tsx
npm run test -- src/pages/__tests__/SettingsPage.test.tsx
npm run test -- src/pages/__tests__/BacktestPage.test.tsx
npm run test -- src/pages/__tests__/MarketOverviewPage.test.tsx
npm run test -- src/pages/__tests__/UserScannerPage.test.tsx
npm run lint
npm run build
./scripts/ci_gate.sh
```

### Verification results

| Command | Result |
| --- | --- |
| `python3 -m py_compile api/v1/endpoints/*.py src/services/*.py src/core/*.py` | Pass |
| `python3 -m pytest tests/api/test_admin_logs.py -q` | 11 passed |
| `python3 -m pytest tests/api/test_system_config.py -q` | 10 passed |
| `python3 -m pytest tests/test_execution_log_service.py -q` | 25 passed |
| `python3 -m pytest tests/test_market_scanner_service.py -q` | 23 passed |
| `python3 -m pytest tests/test_*backtest*.py -q` | 201 passed, 1 warning |
| `npm run test -- src/pages/__tests__/AdminLogsPage.test.tsx` | 10 passed |
| `npm run test -- src/pages/__tests__/SettingsPage.test.tsx` | 64 passed |
| `npm run test -- src/pages/__tests__/BacktestPage.test.tsx` | 23 passed |
| `npm run test -- src/pages/__tests__/UserScannerPage.test.tsx` | 11 passed |
| `npm run test -- src/pages/__tests__/MarketOverviewPage.test.tsx` | 37 passed, 1 failed |
| `npm run lint` | Pass |
| `npm run build` | Pass, with large chunk warnings |
| `./scripts/ci_gate.sh` | Failed: `1 failed, 1831 passed, 2 skipped, 1 warning, 160 subtests passed`; failing test `tests/api/test_market_crypto.py::MarketCryptoApiTestCase::test_crypto_cold_cache_fast_fallback_when_binance_slow` expected `freshness == "fallback"` but got `"live"`. |

### Sanitized excerpts

Unauthenticated auth status:

```json
{
  "authEnabled": true,
  "loggedIn": false,
  "passwordSet": true,
  "passwordChangeable": true,
  "setupState": "enabled",
  "currentUser": null
}
```

Unauthenticated protected API response:

```json
{"error":"unauthorized","message":"Login required"}
```

Guest ORCL preview:

```text
curl: (28) Operation timed out after 130002 milliseconds with 0 bytes received
```

Market Overview frontend test failure:

```text
FAIL src/pages/__tests__/MarketOverviewPage.test.tsx > MarketOverviewPage > keeps other cards visible when one initial API request fails
TestingLibraryElementError: Unable to find an accessible element with the role "heading" and name `/情绪与资金面/i`
```

No screenshots were saved for this audit.
