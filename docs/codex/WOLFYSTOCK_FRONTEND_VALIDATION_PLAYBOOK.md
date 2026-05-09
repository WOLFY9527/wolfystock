# WolfyStock Frontend Validation Playbook

Purpose: standard validation for frontend execution tasks.

Use this playbook together with `WOLFYSTOCK_SHARED_MAIN_WORKTREE_PROTOCOL.md` when working in the shared `main` worktree.

## Standard focused validation

Run focused tests for touched pages/components.

Examples:

```bash
npm --prefix apps/dsa-web run test -- src/pages/__tests__/UserScannerPage.test.tsx
npm --prefix apps/dsa-web run test -- src/pages/__tests__/PortfolioPage.test.tsx
npm --prefix apps/dsa-web run test -- src/pages/__tests__/MarketOverviewPage.test.tsx
npm --prefix apps/dsa-web run test -- src/components/terminal/__tests__/TerminalPrimitives.test.tsx
```

If test file names differ, locate them:

```bash
find apps/dsa-web/src -iname "*Scanner*.test.*" -o -iname "*Portfolio*.test.*" -o -iname "*MarketOverview*.test.*"
```

## Type and build checks

Run when frontend source files are touched:

```bash
npx --prefix apps/dsa-web tsc --noEmit --pretty false --project apps/dsa-web/tsconfig.app.json
npm --prefix apps/dsa-web run build
npm --prefix apps/dsa-web run check:design
```

If the task is small and TypeScript/build is known to be expensive, still prefer build for UI changes unless explicitly instructed otherwise.

## Design guard

Run:

```bash
python3 scripts/check_frontend_design_constitution.py
npm --prefix apps/dsa-web run check:design
```

The guard should catch:
- page-level solid slabs
- local gray/zinc/slate/neutral backgrounds
- loud warning slabs
- user-facing internal terms
- unstyled native controls
- migrated pages not using terminal primitives

## Diff checks

In a clean worktree:

```bash
git diff --check
```

In shared main with foreign dirty files:

```bash
git diff --check -- <TARGET_GLOBS>
```

Before commit:

```bash
git diff --cached --name-only
git diff --cached --check
```

## Secret scan

Run:

```bash
./scripts/release_secret_scan.sh
```

If it fails only because of foreign dirty files from another task, follow `WOLFYSTOCK_SHARED_MAIN_WORKTREE_PROTOCOL.md` and run targeted secret checks on task files only.

## Browser verification

Required for frontend UI changes.

Preferred:
1. Playwright automation.
2. Codex Chrome plugin if available.
3. Manual browser only when automation is impractical.

Do not kill shared dev/backend servers casually.
Inspect common ports:
- backend: `8000`, `8001`
- frontend/dev/preview: `5173`, `4173`, `4177`, `4178`, `5174`, `5175`, `5176`

Prefer task-owned preview port when possible.
Leave shared `5173` untouched unless the task owns it.

## Standard viewports

Use:
- desktop: `1440x1000`
- mobile/narrow: `390x844`

## Browser checks

For each changed route:
- no horizontal overflow
- no console/page errors
- semantic page heading exists if expected
- first viewport hierarchy is usable
- main action visible
- page uses global width rhythm
- no local black/gray slab
- terminal panels/buttons/chips/empty states match other pages
- no forbidden internal terms on user pages
- mobile order makes sense
- sticky/fixed controls do not cover content

## Auth and mocks

If auth is required:
- use `WOLFYSTOCK_TEST_USERNAME`
- use `WOLFYSTOCK_TEST_PASSWORD`
- never print or write passwords

If using mocked API:
- state it clearly in final report
- ensure mock payloads do not create misleading production claims
- do not alter backend behavior to satisfy visual harness

## Route-specific examples

Scanner:
- `/zh/scanner`
- check left control rail on desktop
- `启动扫描` visible in first viewport
- right result stage exists
- candidate cards compact
- selected inspector not repeated everywhere

Portfolio:
- `/zh/portfolio`
- command strip, holdings, risk, activity, manual ledger align
- empty states compact
- manual ledger not dominant by default

Market Overview:
- `/zh/market-overview`
- first fold reads as overview, not warning wall
- data status consolidated
- fallback/stale/mock not marked live

Options:
- `/zh/options-lab`
- full workspace width
- compact status strip
- strategy/assumptions/risk balance
- dense strategy matrix and Call/Put chains

Admin provider:
- `/zh/admin/market-providers`
- no React NaN warning
- diagnostics preserved and layered
- no secrets rendered

## Final report verification section

Include:
- exact commands run
- pass/fail counts
- browser route/viewports
- port used and stopped/left running status
- limitations such as mocked auth/API
- final `git status --short --branch`
