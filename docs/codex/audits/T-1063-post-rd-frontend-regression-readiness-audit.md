# T-1063 Post-RD Frontend Regression Readiness Audit

Task ID: T-1063-AUDIT

Task title: Post-RD frontend regression readiness audit

Mode: READ-ONLY-AUDIT with explicitly authorized docs-only audit artifact, commit, and push.

Allowed artifact:

`docs/codex/audits/T-1063-post-rd-frontend-regression-readiness-audit.md`

Observed workspace:

- cwd: `/Users/yehengli/worktrees/t1063-post-rd-frontend-regression-audit`
- branch: `codex/t1063-post-rd-frontend-regression-audit`
- base commit inspected: `950ec68a`
- pre-write tracked/staged dirty files: none
- local branch commits ahead of `origin/main` during preflight: none

Scope boundary:

- No source, test, config, package, lockfile, screenshot, generated asset, API, backend, provider/cache/runtime, route/auth behavior, or shared primitive files were changed.
- Scanner scoring, ranking, filtering, thresholds, shortlist order, and candidate selection were inspected only.
- Admin Logs filters/tables were inspected only.
- Liquidity/Rotation no-advice and observation-only/readiness copy was inspected only.
- Final diff is limited to this Markdown report.

## Executive decision

No RD-touched frontend source surface needs an immediate source fix from this audit.

Recommend exactly one follow-up task before more frontend source work:

**T-1063-TEST1: Repair Watchlist IA smoke user-alerts mock.**

Why:

- Fresh browser checks on `http://127.0.0.1:8000` found no broken rendering, no horizontal overflow at `390px`, and no obvious console errors on the audited RD-touched routes.
- Existing focused e2e coverage passed for Home chart, Scanner interactions, Watchlist alerts, Market Overview readiness/actionability, Liquidity degraded/readiness copy, Rotation IA, and Admin Logs launch surfaces.
- The only failing evidence is a test-harness gap in `apps/dsa-web/e2e/market-research-surfaces.spec.ts`: the `/zh/watchlist` IA cases do not mock `GET /api/v1/user-alerts/rules`, so the fixture emits a 500 and a console error. The real `/zh/watchlist` browser route did not show that console error.

Do not open a broad frontend redesign, global token migration, shared primitive rewrite, or blanket React Doctor cleanup from this audit.

## Evidence method

- Read the required Codex guard/runtime/final-report docs and `docs/frontend/validation-playbook.md`.
- Used the current selected workspace and branch only.
- Used `http://127.0.0.1:8000`.
- Logged in through the local UI with the admin account supplied by the task.
- Used in-app Browser route checks at `1440x1000` and `390x844`.
- Checked `/guest` in a signed-out session, then restored the admin login.
- Used DOM/test-id checks, console-error collection, horizontal-overflow measurement, and targeted control interaction.
- Captured no committed screenshots and wrote no generated assets. Failed Playwright artifacts remained only under ignored `apps/dsa-web/test-results/`.

## Route verdict matrix

| Route | 1440 desktop verdict | 390 mobile verdict | Console / overflow | Audit verdict |
| --- | --- | --- | --- | --- |
| `/` | Rendered `home-bento-dashboard`, `home-research-console`, and `home-research-chart-section`; title `首页 - WolfyStock`. | Same key surfaces visible. | No console errors; `overflowPx=0`. | Pass. Home ResearchConsole and chart area survived RD cleanup. |
| `/guest` | Signed-in session redirects to `/` as expected. Signed-out `/guest` rendered `guest-home-clean-search` and `guest-home-command-surface`. | Signed-out command surface had `overflowPx=0`. ORCL guest preview completed and rendered `home-research-console`, `home-research-chart-section`, and `home-linear-technical-chart`; data-limited chart fallback stayed safe. | No console errors; no forbidden trading CTA or raw/debug leak. | Pass. Guest default and preview states are usable; chart data can still be unavailable under evidence limits. |
| `/zh/scanner` | Rendered `user-scanner-workspace`; live backend state had `候选 0`, so candidate rows were not available for live clicking. | Same no-candidate state; `scanner-run-button` present. | No console errors; `overflowPx=0`. | Pass with data note. Candidate interactions are covered by focused e2e; live route had no candidates to interact with. |
| `/zh/watchlist` | Rendered `watchlist-page` and `watchlist-filter-grid`. | Same key surfaces visible. | Real browser route had no console errors; `overflowPx=0`. | Pass for product route. Current issue is a smoke fixture gap, not a visible route failure. |
| `/zh/market-overview` | Rendered `market-overview-shell`, `market-decision-semantics-strip`, and `market-overview-decision-readiness`. | Same key readiness/actionability surfaces visible. | No console errors; `overflowPx=0`. | Pass. Readiness/actionability copy remains observation-safe. |
| `/zh/market/liquidity-monitor` | Rendered `liquidity-monitor-guidance-panel` and `liquidity-decision-readiness`. | Same key surfaces visible. | No console errors; `overflowPx=0`. | Pass. Liquidity readiness/observation-only copy remains intact. |
| `/zh/market/rotation-radar` | Initial route sample was loading; after a 12s live wait it rendered `rotation-radar-summary-band`, `rotation-radar-universe-list`, and `rotation-theme-detail-panel`. | 390 sanity had no overflow; focused e2e covered the full content state at 390. | No console errors; `overflowPx=0`. | Pass with latency note. No frontend source issue found. |
| `/zh/admin/logs` | Rendered `admin-logs-workspace` and `admin-logs-filter-bar`; Admin Logs title `管理员日志 - WolfyStock`. | Same key surfaces visible. | No console errors; `overflowPx=0`. | Pass. Tables/filter controls remain usable. |

## Interaction checks

### Scanner

Focused e2e command covered candidate interactions with mocked candidates:

- advanced controls expand;
- theme selector/control visible;
- candidate more-actions panel opens;
- analyze/copy/export/detail buttons are clickable;
- mobile tap heights remain at least `40px`;
- horizontal overflow stays absent;
- candidate interactions did not require source, scoring, ranking, filtering, threshold, or order changes.

Live browser note:

- The real `/zh/scanner` route currently showed `候选 0`, so there were no live candidate rows to click without starting a new scan. This audit did not start a scan because that would create runtime state outside a read-only audit.

### Admin Logs

Real browser interaction on `/zh/admin/logs`:

- `股票分析` tab count: `1`.
- `搜索日志` input count: `1`; value changed to `TSLA`.
- `状态筛选` select count: `1`; value changed to `partial`.
- Filter bar remained visible after interaction.
- No console errors and no horizontal overflow.
- The visible text includes words such as `失败` as business status labels; this was not a page-error signal.

Vitest also covers Admin Logs table/filter behavior, including symbol/status/time-range filtering, pagination reset, scanner/backtest category tabs, sanitized drill-through controls, and detail drawer redaction.

### Home / Guest

- Authenticated `/` rendered the full ResearchConsole and chart area at both viewports.
- Signed-out `/guest` first rendered the command console.
- Guest ORCL preview on `390x844` eventually rendered `home-research-console`, `home-research-chart-section`, and `home-linear-technical-chart`.
- Guest preview remained evidence-limited and showed chart fallback copy instead of a full candlestick data frame, which is acceptable for the current no-advice/evidence-gated product behavior.

### Liquidity / Rotation

- Liquidity live route and degraded e2e both preserved readiness and observation-only copy.
- Rotation live route needed a longer wait but eventually rendered the expected summary, universe list, and detail panel with data-insufficient/readiness copy.
- No buy/sell/order/trade CTA, raw provider payload, debug panel, or developer details were observed in the audited route states.

## Focused validation results

### Playwright e2e

Command:

```bash
WOLFYSTOCK_ADMIN_OPS_ROUTE_FILTER=logs DSA_WEB_PLAYWRIGHT_PORT=4186 npm --prefix apps/dsa-web run test:e2e -- e2e/home-chart-browser.smoke.spec.ts e2e/market-overview-scanner.smoke.spec.ts e2e/watchlist-user-alerts.smoke.spec.ts e2e/market-liquidity-monitor-degraded.spec.ts e2e/market-research-surfaces.spec.ts e2e/admin-ops-launch-surfaces.spec.ts --project=chromium
```

Result:

- `16 passed`
- `2 failed`

Passing coverage included:

- Home chart desktop and `390px`.
- Scanner controls/candidate interactions/copy/export/mobile tap areas.
- Market Overview top metrics/readiness and partial temperature degradation at desktop and `390px`.
- Watchlist user alerts observation-only rail.
- Liquidity degraded proxy-only states at desktop and `390px`.
- Rotation Radar IA at desktop and `390px`.
- Admin Logs launch surface at desktop and `390px` with `WOLFYSTOCK_ADMIN_OPS_ROUTE_FILTER=logs`.

Failure:

- `e2e/market-research-surfaces.spec.ts` `/zh/watchlist` at `1440x1000` and `390x844`.
- Root cause: unhandled mock route `GET /api/v1/user-alerts/rules` in the appSmoke fixture path, producing a 500 and console error.
- Classification: smoke fixture drift. The dedicated `watchlist-user-alerts.smoke.spec.ts` passed and the real browser `/zh/watchlist` route had no console error.

### Vitest

Command:

```bash
npm --prefix apps/dsa-web run test -- src/pages/__tests__/AdminLogsPage.test.tsx src/pages/__tests__/UserScannerPage.test.tsx src/pages/__tests__/HomeSurfacePage.test.tsx src/pages/__tests__/MarketRotationRadarPage.test.tsx src/api/__tests__/liquidityMonitor.test.ts src/api/__tests__/marketRotation.test.ts --no-file-parallelism
```

Result:

- `6 passed`
- `205 passed`

## Current issue list

### Fixed / not current

- No RD display-helper/key/a11y cleanup regression was found in browser route rendering.
- No audited route showed `390px` horizontal overflow.
- No real browser route produced obvious console errors.
- No observed Liquidity/Rotation route promoted evidence-limited states into advice-like or execution wording.
- No Home/Guest ResearchConsole break was found; Home chart renders and Guest preview reaches the chart surface.
- No Admin Logs table/filter break was found.
- No Scanner source scoring/ranking/filtering drift was found; this audit did not edit or exercise protected scanner runtime state.

### Current issue

**Watchlist IA smoke fixture drift**

- File implicated for future task: `apps/dsa-web/e2e/market-research-surfaces.spec.ts`
- Failing cases: `/zh/watchlist prioritizes research flow at 1440x1000` and `/zh/watchlist prioritizes research flow at 390x844`
- Missing mock: `GET /api/v1/user-alerts/rules`
- User-visible route impact: not reproduced in live browser; dedicated Watchlist alerts smoke passed.
- Risk: future RD/frontend changes will have a noisy regression gate until this mock is repaired.

## Recommended next task

Open exactly one follow-up task:

**T-1063-TEST1: Repair Watchlist IA smoke user-alerts mock**

Goal:

- Update `apps/dsa-web/e2e/market-research-surfaces.spec.ts` or its shared fixture setup so the Watchlist IA cases mock `GET /api/v1/user-alerts/rules` with the same owner-scoped, in-app-only empty/safe payload shape used by the dedicated Watchlist alerts smoke.
- Keep the existing Watchlist IA assertions active for both `1440x1000` and `390x844`.
- Do not skip, remove, or narrow the Watchlist route cases.

Allowed future write files:

- `apps/dsa-web/e2e/market-research-surfaces.spec.ts`

Optional only if the repo already has a directly reusable helper and the change can stay test-only:

- `apps/dsa-web/e2e/fixtures/*.ts`

Forbidden future scope:

- No source files.
- No route/auth behavior.
- No API/backend/provider/cache/runtime changes.
- No Watchlist product copy or layout changes.
- No Scanner scoring/ranking/filtering changes.
- No broad React Doctor cleanup.
- No global design primitive rewrite.

Acceptance criteria:

- The full `market-research-surfaces.spec.ts` passes with both Watchlist viewports active.
- `watchlist-user-alerts.smoke.spec.ts` still passes.
- No new `.skip`, `test.fixme`, or grep-only coverage substitution.
- No product source diff.

Suggested validation for the future task:

```bash
DSA_WEB_PLAYWRIGHT_PORT=4187 npm --prefix apps/dsa-web run test:e2e -- e2e/market-research-surfaces.spec.ts e2e/watchlist-user-alerts.smoke.spec.ts --project=chromium
git diff --check -- apps/dsa-web/e2e/market-research-surfaces.spec.ts apps/dsa-web/e2e/fixtures
./scripts/release_secret_scan.sh
```

## Stop decision

Do not proceed to frontend source work from this audit.

First repair the Watchlist IA smoke fixture if the next lane needs a clean post-RD regression gate. After that, stop unless a future task has a fresh, route-specific source regression.

## Final diff confirmation for this audit

- This T-1063 task is report-only.
- Final diff is docs-only and limited to `docs/codex/audits/T-1063-post-rd-frontend-regression-readiness-audit.md`.
- No source files changed.
- No tests changed.
- No config/package/lockfile changes.
- No screenshots or generated assets staged.
- No API/backend/provider/cache/runtime/route/auth behavior changes.
- No Scanner scoring/ranking/filtering changes.
- No broad redesign, shared primitive rewrite, global token migration, or blanket React Doctor cleanup.
