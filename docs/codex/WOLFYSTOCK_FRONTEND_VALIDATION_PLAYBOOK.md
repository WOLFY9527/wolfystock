# WolfyStock Frontend Validation Playbook

Purpose: standard validation for frontend implementation tasks.

Use with:

- `WOLFYSTOCK_CODEX_STANDARD_GUARD.md`
- `CODEX_FRONTEND_DESIGN_CONSTITUTION.md`
- `WOLFYSTOCK_FRONTEND_SURFACE_USAGE.md`
- `WOLFYSTOCK_FRONTEND_ROUTE_TEMPLATES.md`

Default environment:

- Codex App isolated task workspace unless the prompt explicitly uses shared main.
- Local environment: `WolfyStock Fast`.
- Do not run `npm ci`, `npm install`, or `npm audit fix` unless dependency/lock files changed and the task explicitly requires it.

---

## 1. Focused Validation

Run focused tests for touched pages/components.

Examples:

```bash
npm --prefix apps/dsa-web run test -- src/pages/__tests__/HomeSurfacePage.test.tsx --run
npm --prefix apps/dsa-web run test -- src/pages/__tests__/UserScannerPage.test.tsx --run
npm --prefix apps/dsa-web run test -- src/pages/__tests__/WatchlistPage.test.tsx --run
npm --prefix apps/dsa-web run test -- src/pages/__tests__/PortfolioPage.test.tsx --run
npm --prefix apps/dsa-web run test -- src/pages/__tests__/MarketOverviewPage.test.tsx --run
npm --prefix apps/dsa-web run test -- src/components/backtest/__tests__/BacktestResultReport.test.tsx --run
```

If test names differ:

```bash
find apps/dsa-web/src -iname "*Scanner*.test.*" -o -iname "*Portfolio*.test.*" -o -iname "*MarketOverview*.test.*"
```

---

## 2. Build and Design Checks

For frontend source changes, normally run:

```bash
npm --prefix apps/dsa-web run build
npm --prefix apps/dsa-web run check:design
python3 scripts/check_frontend_design_constitution.py
git diff --check
bash scripts/release_secret_scan.sh
```

Run TypeScript check when the task changes types/routes/shared interfaces or build is not enough:

```bash
npx --prefix apps/dsa-web tsc --noEmit --pretty false --project apps/dsa-web/tsconfig.app.json
```

Avoid duplicate `tsc --noEmit` + build unless the extra signal is needed.

`./scripts/ci_gate_fast.sh` is optional worker-iteration evidence. It does not replace task-scoped checks and is not landing proof.

---

## 3. Design Guard Expectations

The guard should prevent:

- card-first dashboard regressions;
- excessive ghost-glass / bento drift;
- broad gray/zinc/slate slabs;
- raw provider/schema/debug/internal copy;
- meta-explanatory UI copy;
- unstyled native controls;
- user-visible internal enum labels;
- excessive side gutters on workbench pages;
- route templates that bury the primary task below secondary diagnostics.

---

## 4. Browser Verification

Required for frontend UI changes unless docs-only/tests-only.

Preferred order:

1. Playwright automation.
2. Codex Chrome plugin if available.
3. Manual browser only when automation is impractical.

Inspect common ports first:

- backend: `8000`, `8001`
- frontend/dev/preview: `5173`, `4173`, `4177`, `4178`, `4179`, `4180`, `5174`, `5175`, `5176`

Leave shared `5173` untouched unless the task owns it. Use a task-owned preview port where possible.

Preferred Playwright invocation from app directory:

```bash
cd apps/dsa-web && DSA_WEB_PLAYWRIGHT_PORT=4177 npx playwright test e2e/<focused-spec>.spec.ts
```

Repo-root is allowed only with explicit config:

```bash
DSA_WEB_PLAYWRIGHT_PORT=4177 npx playwright test --config apps/dsa-web/playwright.config.ts apps/dsa-web/e2e/<focused-spec>.spec.ts
```

Avoid repo-root `npx --prefix apps/dsa-web playwright test ...` when relying on app config.

---

## 5. Standard Viewports

Use:

- desktop: `1440x1000`
- wide desktop: `1920x1080` for wide workspaces
- mobile/narrow: `390x844`

---

## 6. Browser Checks

For each changed route:

- no horizontal overflow;
- no console/page errors;
- semantic page heading exists if expected;
- primary task visible above fold;
- main action visible;
- route follows `WOLFYSTOCK_FRONTEND_ROUTE_TEMPLATES.md`;
- no raw/debug/provider/schema leakage;
- no meta-explanatory UI copy;
- critical warnings remain visible but compact;
- mobile is usable.

For visual redesigns:

- screenshots are required;
- tests alone are not enough;
- final report must include route(s), viewports, and whether screenshots match the intended visual direction.

---

## 7. Diff and Secret Checks

In a clean workspace:

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

If working in shared main with foreign dirty files, follow `WOLFYSTOCK_SHARED_MAIN_WORKTREE_PROTOCOL.md` and stage only task files.
