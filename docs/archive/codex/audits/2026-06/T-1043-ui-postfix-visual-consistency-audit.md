# T-1043 UI post-fix visual consistency audit

Task ID: T-1043-AUDIT
Task title: UI post-fix visual consistency audit
Mode: READ-ONLY-AUDIT with docs-only report artifact
Workspace: `/Users/yehengli/worktrees/t1043-ui-postfix-visual-consistency-audit`
Branch: `codex/t1043-ui-postfix-visual-consistency-audit`
Base commit inspected: `bb987044`

## Decision

Recommend exactly one bounded next write:

**T-1043-FE1 Backtest local radius taxonomy pass**

Fresh browser evidence shows the prior width and spacing fixes mostly landed. The remaining visible cross-surface inconsistency is not a global layout problem: it is the Backtest page's local 24px/32px card radius tier in the first desktop viewport. This is smaller and safer than a global spacing token migration, global radius migration, shared primitive rewrite, or broad Backtest redesign.

## Evidence Method

- Read required guardrails and the prior T-1037 audit.
- Used `http://127.0.0.1:8000`.
- Logged in as an admin account supplied by the prompt.
- Used fresh, no-cache Playwright browser contexts for the final desktop matrix at `1440x1000` and `1920x1080`.
- Used a separate unauthenticated Playwright context for `/guest`.
- Used `390x844` only as cheap overflow sanity.
- Used DOM measurements only; no screenshots, generated assets, source edits, or test/config changes were created.

Important cache note: the in-app browser initially reported `document.title = "WolfyStock"` for Admin Users and Admin Providers. A fresh no-cache Playwright context then held the correct titles for 5 seconds on both routes:

- `/zh/admin/users`: `用户治理 - WolfyStock`
- `/zh/admin/providers` -> `/zh/admin/market-providers`: `数据源运维 - WolfyStock`

Treat the in-app title mismatch as stale cached browser evidence, not a current product issue.

## Fresh Verdict Matrix

Desktop DOM evidence, fresh Playwright contexts:

| Route | 1440 final / title | 1920 main width | Overflow | Radius range | Verdict |
| --- | --- | ---: | --- | --- | --- |
| `/` | `/`, `首页 - WolfyStock` | 1920 | no | 3.4-14 | Fixed: Home width/spacing no longer shows card chaos. |
| `/guest` logged in | `/`, `首页 - WolfyStock` | 1920 | no | 3.4-14 | Expected redirect to Home when authenticated. |
| `/guest` unauthenticated | `/guest`, `游客预览 - WolfyStock` | 1850 | no | 3.4-12 desktop | Fixed: Guest spacing is bounded and local. |
| `/zh/scanner` | `/zh/scanner`, `市场扫描 - WolfyStock` | 1850 | no | 3.4-14 | Fixed shell width; dense board rhythm is intentional. |
| `/zh/portfolio` | `/zh/portfolio`, `持仓分析 - WolfyStock` | 1850 | no | 5.3-16 | Acceptable local ledger density; not a first-write issue. |
| `/zh/market-overview` | `/zh/market-overview`, `WolfyStock` | 1850 | no | 3.4-14 | Width fixed; document title remains generic but outside admin-title scope. |
| `/zh/market/liquidity-monitor` | `/zh/market/liquidity-monitor`, `WolfyStock` | 1850 | no | 3.5-14 | Width fixed; monitor density intentional. |
| `/zh/market/rotation-radar` | `/zh/market/rotation-radar`, `WolfyStock` | 1850 | no | 7-14 | Width fixed; current payload state is compact. |
| `/zh/watchlist` | `/zh/watchlist`, `观察列表 - WolfyStock` | 1850 | no | 5.3-14 | Fixed shell width; row/list density intentional. |
| `/zh/backtest` | `/zh/backtest`, `回测 - WolfyStock` | 1850 | no | 3.4-32 | Width fixed; local radius inconsistency remains visible. |
| `/zh/options-lab` | `/zh/options-lab`, `WolfyStock` | 1850 | no | 3.4-14 | Width fixed; no immediate layout write. |
| `/zh/admin` | redirects to `/zh/settings/system`, `系统设置 - WolfyStock` | 1850 | no | 3.4-24 | Admin title fixed; one settings-local 24px panel remains but is not first write. |
| `/zh/settings/system` | `/zh/settings/system`, `系统设置 - WolfyStock` | 1850 | no | 3.4-24 | Settings/control surface; defer. |
| `/zh/admin/logs` | `/zh/admin/logs`, `管理员日志 - WolfyStock` | 1850 | no | 5.3-14 | Admin title fixed; ops density intentional. |
| `/zh/admin/users` | `/zh/admin/users`, `用户治理 - WolfyStock` | 1850 | no | 5.3-14 | Admin title fixed; ops density intentional. |
| `/zh/admin/providers` | `/zh/admin/market-providers`, `数据源运维 - WolfyStock` | 1850 | no | 5.3-14 | Admin title fixed; alias redirect is expected. |

## Required Issue Checks

### 1. Page max-width inconsistency

Current verdict: fixed enough for this wave.

- Consumer and admin surfaces consistently measured no horizontal overflow at `1440x1000` and `1920x1080`.
- Most product routes now measure `mainWidth=1382.4` at 1440 and `mainWidth=1850` at 1920.
- Home remains more full-bleed (`mainWidth=1440/1920`) because the Home ResearchConsole owns its route-specific stage.
- Admin pages keep inner `max-w-[1600px]` content rails inside a `1850px` main lane. That is a control-plane density choice, not the old consumer shell-width mismatch.

### 2. Home / Guest card chaos and local spacing

Current verdict: fixed.

- Home authenticated: radius range `3.4-14`, no large non-pill panel radii, no horizontal overflow at 1440/1920.
- Guest unauthenticated: radius range `3.4-12`, no horizontal overflow at 1440/1920/390.
- `/guest` while logged in redirects to Home, so the unauthenticated context is the valid Guest evidence.

### 3. Backtest ultrawide width

Current verdict: width fixed.

- Backtest measured `mainWidth=1382.4` at 1440 and `mainWidth=1850` at 1920.
- `backtest-page-shell` measured `1295.6` at 1440 and `1763.2` at 1920 in the detailed DOM pass.
- No horizontal overflow was observed at 1440, 1920, or 390 sanity.

### 4. Admin title gaps

Current verdict: fixed in fresh browser evidence.

- `/zh/admin` redirects to `/zh/settings/system` and sets `系统设置 - WolfyStock`.
- `/zh/admin/logs` sets `管理员日志 - WolfyStock`.
- `/zh/admin/users` sets `用户治理 - WolfyStock`.
- `/zh/admin/providers` redirects to `/zh/admin/market-providers` and sets `数据源运维 - WolfyStock`.

The earlier in-app browser mismatch was stale cached evidence and should not drive another write.

### 5. Remaining card/grid/radius inconsistency

Current verdict: one current visible issue remains.

Backtest still exposes a route-local high-radius tier in the first viewport:

- `backtest-subnav:24`
- `backtest-research-boundary:24`
- `normal-backtest-consolidated-card:32`
- Normal mode summary cards: `24`

Other measured surfaces were either within the 14-16px route shell range or are intentionally dense row/admin boards. System Settings has a `duckdb-quant-panel:24`, but it is a control-plane diagnostic panel and should not outrank the Backtest first-viewport issue.

## Stale / Fixed / Current

### Stale or false-positive findings

- Admin Users and Admin Providers default-title finding from the in-app browser: stale cached chunk evidence. Fresh no-cache Playwright showed correct titles.
- T-1037's Home / Guest local spacing issue: fixed by the post-fix state.
- T-1040/T-1042 Backtest ultrawide-width concern: fixed for shell width and overflow.

### Fixed findings

- Page max-width inconsistency across consumer routes is no longer visible as a blocking issue.
- Home / Guest card chaos is no longer visible in current browser evidence.
- Admin document-title gaps are fixed in fresh browser evidence.
- No requested desktop route showed horizontal overflow.

### Current issue

- Backtest still has page-local 24px/32px first-viewport panel radii. This is visually inconsistent with the surrounding 14px shell surfaces and is small enough for a focused write.

## Recommended Immediate Write

### Task title

T-1043-FE1 Backtest local radius taxonomy pass

### Allowed files

- `apps/dsa-web/src/pages/BacktestPage.tsx`
- `apps/dsa-web/src/components/backtest/NormalBacktestWorkspace.tsx`
- `apps/dsa-web/src/components/backtest/NormalBacktestTemplateInsights.tsx`
- `apps/dsa-web/src/pages/__tests__/BacktestPage.test.tsx`
- `apps/dsa-web/src/components/backtest/__tests__/NormalBacktestWorkspace.test.tsx`

### Forbidden semantics

- Do not change backtest calculations, fills, costs, metrics, stored result semantics, API calls, polling, history loading, sample preparation, rule parsing, defaults, scanner handoff, selected module behavior, or navigation.
- Do not change auth/RBAC, routes, backend, API contracts, providers, cache, runtime, package files, lockfiles, Tailwind config, global tokens, or shared primitives.
- Do not edit `apps/dsa-web/src/index.css` unless fresh evidence proves the listed page/component files cannot resolve the visible Backtest radius issue; if that happens, stop and report instead of widening scope.
- Do not delete, hide, or shorten research boundary evidence, assumptions, rule previews, risk copy, or no-advice framing to reduce density.
- Do not add buy/sell/order/trade/broker CTAs or advice-like copy.
- Do not touch Deterministic/Pro/Historical Backtest surfaces unless the same visible first-viewport issue remains after the allowed normal-mode pass and the task is explicitly widened.

### Visual contract

- Normalize only Backtest first-viewport local shell/panel radii:
  - `backtest-subnav`
  - `backtest-research-boundary`
  - `normal-backtest-consolidated-card`
  - normal-mode template/rule preview cards visible inside the consolidated card
- Target the existing route shell tier (`14px`) for top-level Backtest panels and a smaller local inset tier for nested blocks.
- Preserve the T-1042 width fix: no return to a narrow or over-wide Backtest shell.
- Keep Backtest first viewport focused on the research run workspace and boundary copy.

### Validation commands

Run at minimum:

```bash
npm --prefix apps/dsa-web run check:design
python3 scripts/check_frontend_design_constitution.py
npm --prefix apps/dsa-web run lint
npm --prefix apps/dsa-web run test -- src/pages/__tests__/BacktestPage.test.tsx src/components/backtest/__tests__/NormalBacktestWorkspace.test.tsx --run
npm --prefix apps/dsa-web run build
git diff --check
./scripts/release_secret_scan.sh
```

### Browser measurement requirements

- Use a fresh task-owned preview or confirmed fresh browser context.
- Required route: `/zh/backtest`.
- Required viewports:
  - `1440x1000`
  - `1920x1080`
  - `390x844`
- Required checks:
  - no horizontal overflow;
  - `mainWidth` remains approximately `1382px` at 1440 and `1850px` at 1920;
  - `backtest-page-shell` remains near-full width (`~1296px` at 1440 and `~1763px` at 1920);
  - no first-viewport Backtest non-pill panel radius above the chosen route tier;
  - research boundary copy and no-advice framing remain visible;
  - no console/page errors.

### Risk level

Low to medium.

The change should be class-only and local, but Backtest is a protected product surface. Any need to alter data flow, calculation semantics, route behavior, shared primitives, or global CSS should stop the write.

## Explicit Deferrals

- Defer global spacing token migration.
- Defer global radius migration.
- Defer shared primitive rewrites.
- Defer Home / Guest rewrites.
- Defer Scanner / Watchlist dense-board normalization.
- Defer Admin/Ops density normalization.
- Defer Settings control-plane radius normalization.
- Defer Options Lab and market monitor page-local sweeps.
- Defer deleting or hiding evidence/copy as a density fix.

## Final Diff Boundary

This audit creates only:

- `docs/codex/audits/archive/2026-06/T-1043-ui-postfix-visual-consistency-audit.md`

No source, tests, config, package, lockfile, route, auth, backend, API, provider, cache, runtime, screenshots, or generated assets are changed.
