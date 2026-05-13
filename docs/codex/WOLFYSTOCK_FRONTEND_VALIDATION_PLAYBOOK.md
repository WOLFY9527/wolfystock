# WolfyStock Frontend Validation Playbook

Purpose: standard validation for frontend execution tasks.

Use with:

- `WOLFYSTOCK_CODEX_STANDARD_GUARD.md`
- `WOLFYSTOCK_TERMINAL_PRIMITIVES_USAGE.md`
- `WOLFYSTOCK_FRONTEND_ROUTE_TEMPLATES.md`

Default environment:

- Codex App isolated task workspace.
- Local environment: `WolfyStock Fast`.
- Do not run `npm ci`, `npm install`, or `npm audit fix` unless dependency/lock files changed or the task explicitly requires dependency refresh.

## Standard focused validation

Run focused tests for touched pages/components.

Examples:

```bash
npm --prefix apps/dsa-web run test -- src/pages/__tests__/UserScannerPage.test.tsx
npm --prefix apps/dsa-web run test -- src/pages/__tests__/PortfolioPage.test.tsx
npm --prefix apps/dsa-web run test -- src/pages/__tests__/MarketOverviewPage.test.tsx
npm --prefix apps/dsa-web run test -- src/components/terminal/__tests__/TerminalPrimitives.test.tsx
```

If test names differ:

```bash
find apps/dsa-web/src -iname "*Scanner*.test.*" -o -iname "*Portfolio*.test.*" -o -iname "*MarketOverview*.test.*"
```

## Type, build, and design checks

For frontend source changes, normally run:

```bash
npm --prefix apps/dsa-web run build
npm --prefix apps/dsa-web run check:design
python3 scripts/check_frontend_design_constitution.py
```

Worker default:

```text
- focused tests
- build
- design guard
- focused Playwright on the touched route(s)
```

Run TypeScript check when the task changes types/routes/shared interfaces or build is not sufficient:

```bash
npx --prefix apps/dsa-web tsc --noEmit --pretty false --project apps/dsa-web/tsconfig.app.json
```

Avoid duplicate `tsc --noEmit` + build unless that extra signal is actually needed.

Run file-scoped lint when available and useful. Do not treat unrelated global lint failures as task failures if the touched files lint cleanly; report the unrelated blocker.

`./scripts/ci_gate_fast.sh` is optional worker-iteration feedback. It does not replace the focused frontend checks above, and it is not landing proof.

Reserve full `./scripts/ci_gate.sh` for landing, release, or frontend changes that also widened into shared/high-risk runtime territory.

## Design guard expectations

The guard should catch:

- page-level solid slabs;
- local gray/zinc/slate/neutral backgrounds;
- loud warning slabs;
- user-facing internal terms;
- unstyled native controls;
- migrated pages not using Terminal primitives.

## Diff and secret checks

In a clean isolated workspace:

```bash
git diff --name-status
git diff --check
```

Before commit:

```bash
git diff --cached --name-only
git diff --cached --check
bash scripts/release_secret_scan.sh
```

For write tasks, run `bash scripts/release_secret_scan.sh` before commit/push or landing. Skip it for docs-only/tests-only read-only audits.

When working in shared main with foreign dirty files, use `WOLFYSTOCK_SHARED_MAIN_WORKTREE_PROTOCOL.md`.

## Browser verification

Required for frontend UI changes unless scope is docs-only/tests-only.

Preferred order:

1. Playwright automation.
2. Codex Chrome plugin if available.
3. Manual browser only when automation is impractical.

Inspect common ports first:

- backend: `8000`, `8001`
- frontend/dev/preview: `5173`, `4173`, `4177`, `4178`, `4179`, `4180`, `5174`, `5175`, `5176`

Leave shared `5173` untouched unless the task owns it. Use a task-owned preview port where possible.

For worker tasks, keep Playwright focused on the touched routes and assertions. Do not substitute a broad route sweep for the scoped browser proof the task actually needs.

## Playwright invocation rule

When relying on `apps/dsa-web/playwright.config.ts`, prefer running Playwright from `apps/dsa-web`:

```bash
cd apps/dsa-web && DSA_WEB_PLAYWRIGHT_PORT=4177 npx playwright test e2e/critical-route-launch-smoke.spec.ts --grep "launch smoke"
```

Repo-root is allowed only with explicit config:

```bash
DSA_WEB_PLAYWRIGHT_PORT=4177 npx playwright test --config apps/dsa-web/playwright.config.ts apps/dsa-web/e2e/critical-route-launch-smoke.spec.ts --grep "launch smoke"
```

Avoid repo-root `npx --prefix apps/dsa-web playwright test ...` when relying on app config. It may skip `apps/dsa-web/playwright.config.ts` and miss `baseURL` / preview-server settings.

## Standard viewports

Use:

- desktop: `1440x1000`
- mobile/narrow: `390x844`

## Browser checks

For each changed route:

- no horizontal overflow;
- no console/page errors;
- semantic page heading exists if expected;
- first viewport hierarchy is usable;
- main action visible;
- route follows `WOLFYSTOCK_FRONTEND_ROUTE_TEMPLATES.md`;
- page uses global width rhythm and Terminal primitives where applicable;
- no local black/gray slab;
- no forbidden internal terms on user pages;
- mobile order makes sense;
- sticky/fixed controls do not cover content.

## Auth and mocks

If auth is required:

- use `WOLFYSTOCK_TEST_USERNAME` and `WOLFYSTOCK_TEST_PASSWORD`;
- never print or write passwords.

If using mocked API:

- state it clearly in final report;
- ensure mock payloads do not create misleading production claims;
- do not alter backend behavior to satisfy visual harness.

## Route-specific examples

Scanner:

- `/zh/scanner`
- left control rail visible on desktop;
- `启动扫描` visible in first viewport;
- right result stage exists;
- selected inspector not repeated everywhere.

Portfolio:

- `/zh/portfolio`
- command strip, holdings, risk, activity, manual ledger align;
- empty states compact;
- manual ledger not dominant by default.

Market Overview:

- `/zh/market-overview`
- first fold reads as overview, not warning wall;
- data status consolidated;
- fallback/stale/mock not marked live.

Rotation Radar:

- `/zh/market/rotation-radar`
- market tabs/top-N board/detail panel usable;
- data diagnostics layered;
- no trading instruction copy.

Backtest:

- `/zh/backtest`
- scanner handoff route if touched;
- calculations/results semantics unchanged;
- loading fallbacks compact if lazy boundaries changed.

Options:

- `/zh/options-lab`
- compact status strip;
- strategy/assumptions/risk balance;
- dense strategy matrix and Call/Put chains.

Admin provider:

- `/zh/admin/market-providers` or route under task;
- diagnostics preserved and layered;
- no secrets rendered.

## Final report verification section

Include:

- exact commands and pass/fail counts;
- browser routes/viewports;
- port used and stopped/left running status;
- mocked auth/API limitations;
- final `git status --short --branch`.

For the full report contract, use `WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md`.
