# WolfyStock Frontend Validation Playbook

Purpose: standard validation for frontend execution tasks.

Use with:

- `WOLFYSTOCK_CODEX_STANDARD_GUARD.md`
- `WOLFYSTOCK_LINEAR_OS_DESIGN_LANGUAGE.md`
- `WOLFYSTOCK_FRONTEND_SURFACE_USAGE.md`
- `WOLFYSTOCK_FRONTEND_ROUTE_TEMPLATES.md`
- `WOLFYSTOCK_TERMINAL_PRIMITIVES_USAGE.md`

Default environment:

- Codex App isolated task workspace unless the prompt explicitly scopes shared main.
- Local environment: `WolfyStock Fast`.
- Do not run `npm ci`, `npm install`, or `npm audit fix` unless dependency/lock files changed and the task explicitly requires dependency refresh.

## Standard Focused Validation

Run focused tests for touched pages/components.

Examples:

```bash
npm --prefix apps/dsa-web run test -- src/pages/__tests__/HomeSurfacePage.test.tsx
npm --prefix apps/dsa-web run test -- src/pages/__tests__/UserScannerPage.test.tsx
npm --prefix apps/dsa-web run test -- src/pages/__tests__/WatchlistPage.test.tsx
npm --prefix apps/dsa-web run test -- src/pages/__tests__/PortfolioPage.test.tsx
npm --prefix apps/dsa-web run test -- src/pages/__tests__/MarketOverviewPage.test.tsx
npm --prefix apps/dsa-web run test -- src/components/terminal/__tests__/TerminalPrimitives.test.tsx
```

If names differ:

```bash
find apps/dsa-web/src -iname "*Scanner*.test.*" -o -iname "*Portfolio*.test.*" -o -iname "*MarketOverview*.test.*"
```

## Type, Build, And Design Checks

For frontend source changes, normally run:

```bash
npm --prefix apps/dsa-web run build
npm --prefix apps/dsa-web run check:design
python3 scripts/check_frontend_design_constitution.py
```

Run TypeScript check when the task changes shared interfaces, route typing, or build is insufficient:

```bash
npx --prefix apps/dsa-web tsc --noEmit --pretty false --project apps/dsa-web/tsconfig.app.json
```

Run file-scoped lint when available. Report unrelated lint blockers separately.

`./scripts/ci_gate_fast.sh` is optional worker-iteration evidence. It does not replace focused checks and is not landing proof.

Reserve full `./scripts/ci_gate.sh` for release, landing, or changes that widen into shared/high-risk runtime.

## Diff And Secret Checks

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

For write tasks, run `bash scripts/release_secret_scan.sh` before commit/push or landing. Skip it for read-only audits.

When working in shared main with foreign dirty files, use `WOLFYSTOCK_SHARED_MAIN_WORKTREE_PROTOCOL.md`.

## Browser Verification

Required for frontend UI changes unless scope is docs-only/tests-only.

Preferred order:

1. Playwright automation.
2. Codex Chrome plugin if available.
3. Manual browser only when automation is impractical.

Inspect common ports first:

- backend: `8000`, `8001`
- frontend/dev/preview: `5173`, `4173`, `4177`, `4178`, `4179`, `4180`, `5174`, `5175`, `5176`

Leave shared `5173` untouched unless the task owns it. Use a task-owned preview port where possible.

When relying on `apps/dsa-web/playwright.config.ts`, prefer running Playwright from `apps/dsa-web`:

```bash
cd apps/dsa-web && DSA_WEB_PLAYWRIGHT_PORT=4177 npx playwright test e2e/critical-route-launch-smoke.spec.ts --grep "launch smoke"
```

Repo-root is allowed only with explicit config:

```bash
DSA_WEB_PLAYWRIGHT_PORT=4177 npx playwright test --config apps/dsa-web/playwright.config.ts apps/dsa-web/e2e/critical-route-launch-smoke.spec.ts --grep "launch smoke"
```

## Standard Viewports

Use:

- desktop: `1440x1000`
- wide desktop: `1920x1080` when the route uses broad workspaces
- mobile/narrow: `390x844`

## Browser Checks

For each changed route:

- no horizontal overflow;
- no console/page errors;
- semantic page heading exists if expected;
- first viewport hierarchy is usable;
- main action visible;
- route follows `WOLFYSTOCK_FRONTEND_ROUTE_TEMPLATES.md`;
- page uses global width rhythm and approved primitives;
- no pure-black route island;
- no forbidden internal terms on user pages;
- mobile order makes sense;
- sticky/fixed controls do not cover content.

## Auth And Mocks

If auth is required:

- use `WOLFYSTOCK_TEST_USERNAME` and `WOLFYSTOCK_TEST_PASSWORD`;
- never print or write passwords.

If using mocked API:

- state it clearly in final report;
- ensure mock payloads do not create misleading production claims.
