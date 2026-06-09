# WolfyStock Codex Validation Matrix

Purpose: let future Codex tasks pick the smallest safe validation set instead of defaulting to release-grade validation on every change.

This matrix is local-task guidance. It is not a CI contract and does not make any script mandatory for CI.

## 1. Stop Conditions

Stop immediately and capture the final report before cleanup when any of the following is true:

- Dirty tree exists before a `batch` or `release` run.
- Merge conflict exists: `git diff --name-only --diff-filter=U` returns any file.
- Changed files touch a protected or uncertain domain that this matrix cannot classify safely.
- Any required validation command fails.
- The task would require cleanup of the task worktree or branch before the final report is captured.

Worker iteration may target active local changes, but the worker still stops on merge conflicts, protected-domain uncertainty, or failed validation.

## 2. Validation Tiers

### Worker Focused Gate

Use for a bounded local task before commit when the diff is narrow and the impacted route/module is clear.

Default shape:

- Preflight: `git status --short --branch`
- Route-aware focused tests only
- Changed-file lint/typecheck/build only when frontend source changed
- No release-grade broad sweep
- Playwright only for the impacted route family when UI/auth/route behavior changed

### Batch Integration Fast Gate

Use after a batch of related commits on the task branch, before push, when multiple bounded route families changed but protected runtime domains still did not.

Default shape:

- Clean tree required
- Use branch diff vs `origin/main`
- Run all impacted route-family focused tests
- Run frontend `typecheck` and `build:quiet` when frontend source changed
- Escalate to `./scripts/ci_gate.sh` when backend auth/API, shared frontend infrastructure, unknown paths, workflow/lock changes, or protected-domain uncertainty appear

### Release / UAT Gate

Use only when the task intentionally needs release confidence, cross-surface regression proof, or the diff reached shared/high-risk boundaries.

Default shape:

- Clean tree required
- Full lint/build gates
- Full route-family Playwright for all impacted surfaces
- `./scripts/ci_gate.sh` for backend/runtime/auth/API/shared-risk changes
- Additional browser/UAT evidence as required by the task prompt

## 3. Lint / Build Rules

Run frontend lint/build only when the changed files justify it.

### Required

- `npm --prefix apps/dsa-web run lint:changed`
  - Any change under `apps/dsa-web/src/**`
  - Any change under `apps/dsa-web/scripts/**`
  - Any frontend config/test harness change that can affect imports, route wiring, or TS/ESLint resolution
- `npm --prefix apps/dsa-web run typecheck`
  - Any change under `apps/dsa-web/src/**`
  - Any route, shared component, hook, util, API client, or auth-related frontend change
- `npm --prefix apps/dsa-web run build:quiet`
  - Any change under `apps/dsa-web/src/**`
  - Any route entry, shared UI primitive, CSS/token, or router/auth shell change
- `npm --prefix apps/dsa-web run lint`
  - Release/UAT gate
  - Shared frontend infrastructure changes such as `src/components/**`, `src/hooks/**`, `src/utils/**`, `src/styles/**`, route shell, or router entry
- `npm --prefix apps/dsa-web run build`
  - Release/UAT gate
  - Any change that already required full `lint`

### Skipped

- Docs-only changes
- Shell/helper script changes outside `apps/dsa-web/`
- Pure Playwright spec or Vitest-only changes when no frontend runtime source changed

## 4. Playwright Worker Rules

Always use a task-owned `DSA_WEB_PLAYWRIGHT_PORT`.

Use `--workers=2` only when all of the following are true:

- Tier is `worker` or `batch`
- Exactly one impacted route family is selected
- Selected specs are mocked/local route checks, not shared-session or release-style sweeps
- No guest/auth/router flow, backend auth/API flow, admin rail contract, viewport canonicalization, or cross-route smoke is included

Use `--workers=1` when any of the following is true:

- Tier is `release`
- More than one route family is impacted
- Any auth/session/redirect behavior is involved
- Any admin/observability route is involved
- Any canonicalization, shared shell, or broad smoke spec is involved
- You are unsure

## 5. Pattern-To-Validation Map

The file-pattern examples below are intentionally conservative. If a task hits more than one family, union the recommended tests and drop Playwright to `--workers=1`.

| Family | Typical changed paths | Recommended worker gate | Recommended batch fast gate | Release / UAT escalation |
| --- | --- | --- | --- | --- |
| guest/auth/router | `apps/dsa-web/src/__tests__/AppRoutes.test.tsx`, `apps/dsa-web/src/components/auth/**`, `apps/dsa-web/src/contexts/**Auth**`, `apps/dsa-web/src/pages/**Guest**`, `**LoginPage**`, `**ResetPasswordPage**`, `apps/dsa-web/e2e/guest-entry-branding.smoke.spec.ts`, `apps/dsa-web/e2e/product-auth-harness.spec.ts`, `apps/dsa-web/e2e/viewport-route-canonicalization.smoke.spec.ts`, `apps/dsa-web/e2e/smoke.spec.ts` | Vitest: `AppRoutes`, `AuthContext`, `AuthGuardOverlay`, impacted guest/login page tests. Playwright: `guest-entry-branding.smoke.spec.ts` plus one auth/route spec. `workers=1`. | Add `typecheck` + `build:quiet`. Include both guest branding and one route/auth harness spec. | Full `lint` + `build`; run all impacted auth/route specs and broad smoke if redirect semantics changed. |
| market/home | `apps/dsa-web/src/pages/Home*`, `HomeSurfacePage`, `MarketOverviewPage`, `apps/dsa-web/src/api/**market**`, `apps/dsa-web/e2e/home-*.spec.ts`, `market-overview*.spec.ts`, `readiness-browser-acceptance.smoke.spec.ts` | Vitest: `HomeSurfacePage`, `MarketOverviewPage`, relevant `src/api/__tests__/market*.test.ts`. Playwright: `home-chart-browser.smoke.spec.ts`, `home-fundamentals-summary.spec.ts`, `market-overview-scanner.smoke.spec.ts` as needed. `workers=2` allowed only for single-family mocked specs. | Add `lint:changed`, `typecheck`, `build:quiet`. Include impacted home/market specs. | Full `lint` + `build`; add readiness/critical route smoke when route semantics or research-state copy changed. |
| scanner/watchlist | `apps/dsa-web/src/pages/**Scanner**`, `**Watchlist**`, `apps/dsa-web/src/api/**scanner**`, `**watchlist**`, `apps/dsa-web/e2e/scanner-*.spec.ts`, `watchlist-*.spec.ts`, `home-scanner-evidence-browser.smoke.spec.ts` | Vitest: `ScannerSurfacePage`, `UserScannerPage`, `WatchlistPage`, `src/api/__tests__/scanner.test.ts`, `watchlist.test.ts`, `userAlerts.test.ts` as needed. Playwright: `scanner-launch-surface.spec.ts`, `watchlist-empty-state-cta.spec.ts`, `watchlist-user-alerts.smoke.spec.ts`. `workers=2` allowed only for one family and mocked specs. | Add `lint:changed`, `typecheck`, `build:quiet`. If scanner and watchlist both changed, force `workers=1`. | Full `lint` + `build`; add readiness/public-safety scanner smoke when user-facing safety or evidence copy changed. |
| portfolio | `apps/dsa-web/src/pages/**Portfolio**`, `apps/dsa-web/src/components/portfolio/**`, `apps/dsa-web/src/api/**portfolio**`, `apps/dsa-web/e2e/portfolio-*.spec.ts` | Vitest: `PortfolioPage`, `PortfolioScenarioRiskPanel`, `src/api/__tests__/portfolio.test.ts`. Playwright: `portfolio-launch-surface.spec.ts`, `portfolio-empty-state-cta.spec.ts` when entry UX changed. Default `workers=1`. | Add `lint:changed`, `typecheck`, `build:quiet`. | Full `lint` + `build`; add broader smoke if auth boundary or IBKR sync entry semantics changed. |
| options | `apps/dsa-web/src/pages/**Options**`, `apps/dsa-web/src/api/**options**`, `apps/dsa-web/e2e/public-safety-ai-scanner-options.smoke.spec.ts` | Vitest: `OptionsLabPage`, `src/api/__tests__/optionsLab.test.ts`. Playwright: `public-safety-ai-scanner-options.smoke.spec.ts`. Default `workers=1`. | Add `lint:changed`, `typecheck`, `build:quiet`. | Full `lint` + `build`; escalate to protected-domain review if ranking/gates/payoff/API shape is touched. |
| liquidity/rotation | `apps/dsa-web/src/pages/**Liquidity**`, `**Rotation**`, `apps/dsa-web/src/api/**liquidity**`, `**marketRotation**`, `apps/dsa-web/e2e/market-liquidity-monitor-degraded.spec.ts`, `market-rotation-observation-themes.spec.ts`, `rotation-radar-loading-polish.smoke.spec.ts` | Vitest: `LiquidityMonitorPage`, `MarketRotationRadarPage`, `src/api/__tests__/liquidityMonitor.test.ts`, `marketRotation.test.ts`. Playwright: impacted liquidity/rotation specs. `workers=2` allowed only for a single one of liquidity or rotation. | Add `lint:changed`, `typecheck`, `build:quiet`. If both liquidity and rotation changed, use `workers=1`. | Full `lint` + `build`; add `ux-audit-p0-verification.smoke.spec.ts` when consumer-safe route copy or layout density changed. |
| backend auth/API | `api/**auth**`, `api/v1/endpoints/**`, `tests/test_auth_route_capability_inventory.py`, `apps/dsa-web/src/api/**`, frontend auth clients that depend on backend contract | Focused pytest first. If auth/API contract or route capability inventory changed, go straight to `./scripts/ci_gate.sh`. Frontend route tests only when the backend contract change impacts the web boundary. | `./scripts/ci_gate.sh` required. Add impacted frontend build/tests if web client changed. | Release-grade gate by default. |
| admin/observability | `apps/dsa-web/src/pages/**Admin**`, `apps/dsa-web/src/components/admin/**`, `apps/dsa-web/src/api/**admin**`, `apps/dsa-web/e2e/admin-*.spec.ts`, `admin-rail-contract.smoke.spec.ts`, `admin-ops-launch-surfaces.spec.ts`, `admin-evidence-workflow.spec.ts` | Vitest: impacted admin page/component/api tests. Playwright: impacted admin spec(s). `workers=1`. | Add `lint:changed`, `typecheck`, `build:quiet`. Keep `workers=1`. | Full `lint` + `build`; run all impacted admin specs and any contract smoke touched by the change. |
| docs-only | `docs/**`, `*.md`, `scripts/codex/*.sh` when the change is docs/helper only | `git diff --check`, `bash -n` for changed shell helpers, optional `./scripts/release_secret_scan.sh` when publishing-sensitive docs changed | Same as worker unless batch intentionally bundles script changes | No extra escalation unless the docs describe new release/ops behavior that must be proven separately |

## 6. Helper Script Usage

Optional helper:

```bash
bash scripts/codex/run_impacted_validation.sh --plan
bash scripts/codex/run_impacted_validation.sh --tier worker --run
bash scripts/codex/run_impacted_validation.sh --tier batch --source branch --run
```

Properties:

- Conservative and inspectable shell only
- No dependency installation
- No network assumption beyond commands already used in this repo
- Not required by CI
- Falls back to explicit manual commands when the path family is unknown or too broad

## 7. Common Examples

### Docs-only Codex task

```bash
bash scripts/codex/run_impacted_validation.sh --tier worker --plan
git diff --check
```

### Guest/auth copy or redirect adjustment

```bash
bash scripts/codex/run_impacted_validation.sh --tier worker --source active --run
```

Expected shape:

- `lint:changed`
- focused auth/guest Vitest
- one or two auth/guest Playwright specs with `--workers=1`
- `typecheck`
- `build:quiet`

### Home/market route copy or component polish

```bash
bash scripts/codex/run_impacted_validation.sh --tier worker --source active --run
```

Expected shape:

- `lint:changed`
- focused home/market Vitest
- one or two mocked home/market Playwright specs
- `typecheck`
- `build:quiet`

### Batch of scanner + watchlist changes before push

```bash
bash scripts/codex/run_impacted_validation.sh --tier batch --source branch --run
```

Expected shape:

- clean tree check
- impacted scanner/watchlist Vitest
- impacted Playwright with `--workers=1`
- `typecheck`
- `build:quiet`

### Backend auth/API contract task

```bash
bash scripts/codex/run_impacted_validation.sh --tier batch --source branch --plan
./scripts/ci_gate.sh
```

## 8. Cleanup Rule

Do not cleanup the task worktree or branch before the final report is captured.

Cleanup is safe only after:

- validation results are recorded,
- commit/push status is recorded,
- final `git status --short --branch` is captured,
- and the final report explicitly says cleanup is safe.
