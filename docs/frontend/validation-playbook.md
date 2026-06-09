# WolfyStock Frontend Validation Playbook

Status: current frontend validation authority.

This playbook consolidates the former frontend validation playbook, Codex
visual evidence protocol, UX density harness note, and CSS cleanup audit
guardrails. It applies to frontend UI implementation, redesign, visual audit,
route migration, and CSS cleanup tasks.

## Standard Commands

For most frontend UI tasks, run:

```bash
npm --prefix apps/dsa-web run check:design
python3 scripts/check_frontend_design_constitution.py
npm --prefix apps/dsa-web run lint
npm --prefix apps/dsa-web run build
npm --prefix apps/dsa-web run test -- <focused-test-files>
git diff --check
./scripts/release_secret_scan.sh
```

Run broader tests only when the changed surface, shared primitive, API contract,
or release risk warrants it.

## Validation Tiers

Changed-file tooling is an iteration accelerator, not a release waiver. The
shared collector is:

```bash
python3 scripts/validation_changed_files.py --mode active --format lines
```

It filters generated/static/binary/build/cache/dependency artifacts by default.
Use `--scope frontend-lint`, `--scope frontend-related`, `--scope design`,
`--scope python`, `--scope docs`, or `--scope secret` to feed focused tools.

Recommended tier commands:

```bash
# copy-only/docs
git diff --check
./scripts/release_secret_scan.sh --local-only

# frontend-component
npm --prefix apps/dsa-web run lint:changed
npm --prefix apps/dsa-web run test:related -- <app-relative-source-or-test-file>
npm --prefix apps/dsa-web run check:design:changed
npm --prefix apps/dsa-web run typecheck
npm --prefix apps/dsa-web run build:quiet
./scripts/release_secret_scan.sh --local-only

# frontend-shared
npm --prefix apps/dsa-web run lint:changed
npm --prefix apps/dsa-web run test:related:changed
npm --prefix apps/dsa-web run check:design:changed
npm --prefix apps/dsa-web run typecheck
npm --prefix apps/dsa-web run build:quiet
./scripts/release_secret_scan.sh --local-only

# backend-report
python3 -m py_compile <changed_python_files>
python3 -m pytest -q <focused_report_tests>
git diff --check
./scripts/release_secret_scan.sh --local-only

# protected-domain
./scripts/ci_gate_fast.sh
# If the fast gate classifies protected/unknown/full-gate risk, it escalates to:
./scripts/ci_gate.sh
./scripts/release_secret_scan.sh

# batch-land
./scripts/ci_gate_fast.sh
git diff --check
./scripts/release_secret_scan.sh

# release-gate
./scripts/ci_gate.sh
npm --prefix apps/dsa-web run lint
npm --prefix apps/dsa-web run build
npm --prefix apps/dsa-web run check:design
./scripts/release_secret_scan.sh
```

`build:quiet` still fails on TypeScript or Vite errors; it only reduces noisy
successful Vite output. `release_secret_scan.sh` defaults to the release-safe
branch + staged + working tree + untracked scan. Use `--local-only` only for
inner-loop validation, and `--files-from <path>` only when a caller already has
a reviewed changed-file list.

## Standard Playwright Invocation

When frontend E2E validation is needed, run Playwright through the app-local
package script so `apps/dsa-web/playwright.config.ts` loads its `baseURL` and
`webServer` settings:

```bash
DSA_WEB_PLAYWRIGHT_PORT=4181 npm --prefix apps/dsa-web run test:e2e -- e2e/market-research-surfaces.spec.ts --project=chromium
```

Equivalent app-local form:

```bash
cd apps/dsa-web
DSA_WEB_PLAYWRIGHT_PORT=4181 npx playwright test e2e/market-research-surfaces.spec.ts --project=chromium
```

Do not use these command shapes for config-dependent frontend E2E validation:

```bash
npx playwright test apps/dsa-web/e2e/market-research-surfaces.spec.ts --project=chromium
npx --prefix apps/dsa-web playwright test e2e/market-research-surfaces.spec.ts --project=chromium
```

Those forms can bypass the app-local Playwright config and cause relative
`page.goto('/...')` navigations to fail with invalid URL errors.

## Authenticated Route Smoke Standard

For auth-gated frontend route smoke checks, prefer app-local Playwright
harnesses over ad-hoc manual browser login:

- Use `apps/dsa-web/e2e/fixtures/authenticatedRouteSmoke.ts` when the route
  only needs a normal authenticated session plus route-specific API mocks from
  the spec or an existing fixture. The helper installs mocked
  `/api/v1/auth/status` and `/api/v1/auth/me`, opens the route, captures API
  request paths, records console/page errors, exposes a no-horizontal-overflow
  assertion, and provides cleanup through
  `page.unrouteAll({ behavior: 'ignoreErrors' })`.
- Use `apps/dsa-web/e2e/fixtures/productAuth.ts` for product routes such as
  Options Lab that need the existing product data mocks and product request
  assertions.
- Use `apps/dsa-web/e2e/fixtures/adminAuth.ts` for Admin/Ops routes that need
  admin API payload mocks, RBAC capability rehearsal, or admin-only request
  assertions. The generic authenticated route smoke helper may mock an admin
  auth status, but it does not replace the admin harness for admin data routes.
- Keep route paths exact and canonical. For example, use
  `/zh/market/rotation-radar` instead of the legacy mismatch
  `/zh/rotation-radar`.

Manual browser, Safari, or in-app browser evidence is acceptable only as
supplemental evidence or when Playwright/local preview is blocked by a concrete
environment issue. It should not replace a focused Playwright auth harness for
auth-gated route acceptance when the app-local harness can run.

Temporary screenshots for manual or fallback browser evidence must stay outside
the repo:

```text
/tmp/<task-id>-fresh-before/
/tmp/<task-id>-fresh-after/
```

When browser evidence is blocked, report it directly in the final report with:

- command or browser target attempted;
- exact blocker, such as localhost access denied, `ERR_CONNECTION_CLOSED`, or
  auth-gated route redirect;
- whether Playwright E2E, request logs, console/page errors, and
  no-horizontal-overflow checks still ran;
- confirmation that no stale screenshots or old `/tmp` images were used as
  current proof.

## Fresh Evidence Rule

Current UI evidence must come only from:

1. current HEAD;
2. fresh build;
3. fresh task-owned dev/preview server;
4. fresh browser capture during the current task.

Do not use existing images from `/tmp`, `screenshots/`, `artifacts/`,
`apps/dsa-web/test-results/`, `apps/dsa-web/playwright-report/`,
`apps/dsa-web/blob-report/`, `docs/`, repo image files, uploaded/reference
images, old visual snapshots, or search results as current UI proof.

The mockup at `docs/design/reference/wolfystock-reflect-linear-home-mockup.png`
is a visual target, not current implementation evidence.

## Visual Preflight

Before relying on screenshots for a visual task:

```bash
pwd
git status --short --branch
git log --oneline -8
git diff --name-only
git diff --cached --name-only
lsof -i :5173 -i :4173 -i :4177 -i :4178 -i :4179 -i :4180 -i :4181 || true
npm --prefix apps/dsa-web run build
```

Use a task-owned port. Prefer one not already in use:

```bash
cd apps/dsa-web
DSA_WEB_PLAYWRIGHT_PORT=4181 npx vite preview --host 127.0.0.1 --port 4181
```

Open only the task-owned URL, for example:

```text
http://127.0.0.1:4181/
```

## Screenshot Locations And Viewports

Fresh before screenshots:

```text
/tmp/<task-id>-fresh-before/
```

Fresh after screenshots:

```text
/tmp/<task-id>-fresh-after/
```

Do not save current-task screenshots into tracked repo paths unless the task
explicitly asks for committed visual artifacts.

Default route-level viewports:

```text
1440x1000
1920x1080
390x844
```

For dense boards/tables, also inspect horizontal overflow and row action
behavior on mobile.

## Route Visual Gates

For every migrated route, verify:

- primary work region is visible in the first viewport;
- filters are compact;
- rail is bounded;
- diagnostics/details are collapsed or contained;
- no uncontrolled card wall remains;
- no raw `Details` copy appears;
- empty state is compact and attached to the primary surface;
- mobile stacks the primary task first;
- no horizontal overflow appears;
- no console or page errors appear.

Route-specific gates:

| Route family | Required visual proof |
| --- | --- |
| Home | One dominant ResearchConsole; chart is primary; rail and event deck sit inside console rhythm |
| Scanner | Ranking rows/table dominate; selected detail is bounded; diagnostics/backtest collapsed |
| Watchlist | Watch rows/list dominate; filters do not own first viewport; empty state is compact |
| Chat | Conversation ScrollPanel bounded; composer anchored; evidence/context rail collapsed or bounded |
| Market Overview | Market state is primary; indicator boards equalized and contained |
| Liquidity | Liquidity score and signal table primary; source/risk rail is bounded |
| Rotation | Ranked themes/sectors primary; selected theme detail contained |
| Portfolio | Holdings ledger primary; risk rail bounded |
| Options | Decision matrix/strategy rows primary; chain/payoff details contained |
| Backtest | Result/compare workspace primary; parameters/details contained |
| Admin/Ops | Operation queue/table primary; status/actions rail grouped and low-noise |

Mark a route as visually weak when screenshots show renamed layout classes but
the old card sprawl, secondary dominance, generic dashboard-kit shape, or
unclear hierarchy remains.

## UX Density Harness

`apps/dsa-web/e2e/ux-density-audit.spec.ts` is a local Playwright harness for
reviewing first-viewport overload. It is not CI-blocking by default; it emits
structured metrics for review.

Run it with an isolated preview port:

```bash
DSA_WEB_PLAYWRIGHT_PORT=<free-port> npm --prefix apps/dsa-web run test:e2e -- e2e/ux-density-audit.spec.ts --project=chromium
```

Default report path:

```text
apps/dsa-web/test-results/ux-density-audit-report.json
```

Optional output override:

```bash
UX_DENSITY_AUDIT_OUTPUT=/tmp/wolfystock-ux-density-audit.json \
DSA_WEB_PLAYWRIGHT_PORT=<free-port> \
npm --prefix apps/dsa-web run test:e2e -- e2e/ux-density-audit.spec.ts --project=chromium
```

The report path is a test output or temporary path and should not be committed.
The hard assertions are no horizontal overflow, no console/page errors, and no
visible raw secret-like content. Card count, control count, raw-term hits,
glossary/help affordance count, first heading, and first-viewport content order
are review metrics.

## CSS Cleanup Guardrails

CSS deletion or splitting needs stronger proof than static search. Before
removing a selector family:

- search source and tests by exact selector;
- inspect dynamic composition paths such as shell route modifiers;
- render affected routes and inspect DOM;
- capture desktop/mobile screenshots from the current task server;
- run build, design guard, focused tests, `git diff --check`, and secret scan.

Treat shell route modifiers such as `theme-shell--*`,
`shell-content-frame--*`, `shell-main-column--*`, and active report/backtest
primitives as protected until route visual coverage proves an edit is safe.

Archived CSS audits under `docs/frontend/archive/` preserve provenance only;
use this playbook and current source/tests for current deletion decisions.

## Required Report Fields

Frontend final reports should include:

```text
Fresh screenshot source:
- URL:
- Port:
- Server ownership:
- Build command:
- Screenshot paths:
- Confirmation screenshots were captured live during this task:
```

And:

```text
Visual checks:
- no horizontal overflow
- no console/page errors
- no pure-black root gutters/gaps
- route follows the frontend surface taxonomy
- no stale/reference screenshot was used as current UI evidence
```

When density is in scope, also report:

- first desktop viewport content order;
- first mobile viewport meaningful content order;
- visible summary card counts;
- whether diagnostics/provider/cache/raw fields and tables are collapsed by
  default;
- whether professional terms received tooltip, helper text, disclosure, or
  drilldown treatment;
- confirmation there is no buy/sell/order/trade CTA unless explicitly
  requested and safety-reviewed.

## Stop Conditions

Stop and report instead of claiming visual success when:

- a fresh preview server cannot be started;
- the route renders from an old port or stale bundle;
- browser screenshots cannot be captured;
- the page still visibly matches a forbidden old pattern;
- screenshot evidence came from old files or search results;
- tests pass but the visual gate fails.
