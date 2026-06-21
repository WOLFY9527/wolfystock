# T-1028 Frontend validation flake and command reliability audit

Task ID: T-1028-AUDIT

Task title: Frontend validation flake and command reliability audit

Mode: READ-ONLY-AUDIT with one explicitly allowed audit artifact.

Allowed artifact: `docs/codex/audits/T-1028-frontend-validation-flake-command-reliability-audit.md`

Observed workspace: `/Users/yehengli/worktrees/t1028-frontend-validation-flake-audit`

Observed branch: `codex/t1028-frontend-validation-flake-audit`

Observed base commit before artifact: `7658ab01`

Scope boundary:

- No source changes.
- No test changes.
- No script, config, package, lockfile, CI, Playwright config, or Vitest config changes.
- This audit classifies failure modes and proposes future bounded fixes only.

## Executive summary

The highest-value reliability improvement is not a broad frontend validation
rewrite. The current friction splits into two classes:

1. prompt/command mistakes that can be avoided immediately with shell-safe
   templates; and
2. real Backtest test-suite risk from async React updates, stateful mocks, and
   dynamic import gates.

The safest near-term path is:

- use quoted Vitest filters and Vitest-native serial options in future prompts;
- give Playwright each concurrent attempt a unique preview port, or avoid
  parallel Playwright attempts entirely;
- schedule one tests-only Backtest reliability task;
- optionally schedule one docs-only command-template task.

No future source/runtime fix is recommended from this audit alone.

## Evidence inspected

Targeted files and commands inspected:

- `apps/dsa-web/package.json`
- `apps/dsa-web/vitest.config.ts`
- `apps/dsa-web/playwright.config.ts`
- `apps/dsa-web/src/setupTests.ts`
- `apps/dsa-web/src/pages/__tests__/BacktestPage.test.tsx`
- `apps/dsa-web/src/pages/__tests__/BacktestPage.lazy.test.tsx`
- `apps/dsa-web/src/pages/__tests__/DeterministicBacktestResultPage.test.tsx`
- `apps/dsa-web/src/pages/tests/DeterministicBacktestResultPage.test.tsx`
- `apps/dsa-web/src/pages/__tests__/HomeSurfacePage.test.tsx`
- selected Playwright fixture route harnesses under `apps/dsa-web/e2e/fixtures/`
- prior audit context in `docs/codex/audits/archive/2026-06/T-987-post-wave-react-doctor-smoke-stability-audit.md`
- prior fixture audit context in `docs/codex/audits/archive/2026-06/T-990-smoke-fixture-consolidation-audit.md`

Key config facts:

- `apps/dsa-web/package.json:11` defines `test` as `vitest run`.
- `apps/dsa-web/package.json:12` defines `test:e2e` as `playwright test`.
- `apps/dsa-web/vitest.config.ts:6-10` uses jsdom setup and does not override
  Vitest's default file parallelism or file isolation.
- `apps/dsa-web/playwright.config.ts:3-13` defaults preview port to `4173` and
  reuses an existing local server outside CI.
- `apps/dsa-web/src/setupTests.ts:1-72` provides browser API mocks, but not a
  global mock reset policy.

## Prompt and command mistakes

These are not product flakes.

### 1. zsh glob expansion before Vitest starts

Unquoted globs or bracket-like patterns can fail in zsh before `vitest run` gets
the filter. The failure mode belongs to the shell, not Vitest.

Use quoted package-root filters after `--`:

```bash
npm --prefix apps/dsa-web run test -- 'src/pages/__tests__/BacktestPage.test.tsx' --reporter=dot
```

For multiple files:

```bash
npm --prefix apps/dsa-web run test -- 'src/pages/__tests__/BacktestPage.test.tsx' 'src/pages/__tests__/BacktestPage.lazy.test.tsx' 'src/pages/__tests__/DeterministicBacktestResultPage.test.tsx' 'src/pages/tests/DeterministicBacktestResultPage.test.tsx' --reporter=dot
```

If a glob is truly needed, quote the entire glob:

```bash
npm --prefix apps/dsa-web run test -- 'src/pages/**/__tests__/*.test.tsx' --reporter=dot
```

### 2. Jest-style `--runInBand` is invalid for this Vitest version

Observed command:

```bash
npm --prefix apps/dsa-web run test -- 'src/pages/__tests__/BacktestPage.test.tsx' 'src/pages/__tests__/BacktestPage.lazy.test.tsx' 'src/pages/__tests__/DeterministicBacktestResultPage.test.tsx' 'src/pages/tests/DeterministicBacktestResultPage.test.tsx' --runInBand --reporter=dot
```

Observed result:

- failed before test execution;
- Vitest emitted `CACError: Unknown option --runInBand`.

Use Vitest-native serial file execution:

```bash
npm --prefix apps/dsa-web run test -- 'src/pages/__tests__/BacktestPage.test.tsx' 'src/pages/__tests__/BacktestPage.lazy.test.tsx' 'src/pages/__tests__/DeterministicBacktestResultPage.test.tsx' 'src/pages/tests/DeterministicBacktestResultPage.test.tsx' --no-file-parallelism --reporter=dot
```

Observed result for that safer command:

- `4 passed (4)` test files;
- `61 passed (61)` tests;
- React `act(...)` warnings still appeared from Backtest tests.

### 3. Path filters are relative to the package root

When using `npm --prefix apps/dsa-web`, pass Vitest filters relative to
`apps/dsa-web`, not the repository root. Prefer:

```bash
npm --prefix apps/dsa-web run test -- 'src/pages/__tests__/HomeSurfacePage.test.tsx' --reporter=dot
```

Avoid:

```bash
npm --prefix apps/dsa-web run test -- apps/dsa-web/src/pages/__tests__/HomeSurfacePage.test.tsx
```

## Actual flakes or real reliability risks

### 1. Backtest still emits React `act(...)` warnings

The combined Backtest command passed, but emitted warnings from
`BacktestPage.test.tsx`:

- `BacktestPage > loads executable catalog templates without showing the unsupported warning`
- `BacktestPage > renders English shell copy on localized routes`

The warning is a real test hygiene signal because the suite performs many
interactive updates with `fireEvent` and asynchronous effects. Examples include:

- helper interactions in `BacktestPage.test.tsx:576-593`;
- default mock setup in `BacktestPage.test.tsx:595-904`;
- advanced drawer/toggle interactions in `BacktestPage.test.tsx:1190-1235`;
- unsupported guidance interactions in `BacktestPage.test.tsx:1249-1265`.

This is an actual reliability risk, not a shell mistake. It did not fail the
two audit runs, but warnings can hide unawaited state updates that later turn
into order-dependent assertions.

### 2. Backtest mocks are stateful across many tests

The likely source of order-dependent Backtest failures is stale mock
implementation state, especially one-shot implementations and dynamic import
gates.

Evidence:

- `BacktestPage.test.tsx:595-904` uses `vi.clearAllMocks()` in `beforeEach`,
  then assigns default implementations for many API mocks.
- The same file later uses `mockResolvedValueOnce`, `mockRejectedValueOnce`, and
  per-test `mockImplementation` overrides.
- `DeterministicBacktestResultPage.test.tsx:378-402` also uses
  `vi.clearAllMocks()` with stateful globals and import gates.
- `DeterministicBacktestResultPage.test.tsx:32-124` defines hoisted
  `auditTablesImportGate` and `reportImportGate` that can delay dynamic imports.
- `DeterministicBacktestResultPage.test.tsx:510-530` mixes fake timers,
  pending async UI work, and `vi.dynamicImportSettled()`.
- `DeterministicBacktestResultPage.test.tsx:1379-1411` and `:1492-1649` use
  one-shot and custom mock implementations in later tests.
- `src/pages/tests/DeterministicBacktestResultPage.test.tsx:14-52` is a second
  result-page test file with its own hoisted mocks for the same API and report
  components.

`vi.clearAllMocks()` clears call history; it is not a reliable reset boundary
for mock implementations and one-shot queues. A future tests-only pass should
use explicit `mockReset()` or `vi.resetAllMocks()` plus per-test default
restoration where needed.

### 3. Lazy import tests intentionally park unresolved chunks

`BacktestPage.lazy.test.tsx:23` mocks
`../../components/backtest/NormalBacktestWorkspace` as `new Promise(() => {})`.
That is useful for proving the loading shell, but it should remain isolated.
Combining this style with disabled file isolation or broad module-cache changes
would be risky.

Keep future prompts away from `--no-isolate` for Backtest unless the task is
explicitly investigating module isolation.

## Playwright concurrency, webserver, and mock collision risks

The Playwright config is serial inside one run, but not safe for casual parallel
attempts:

- `apps/dsa-web/playwright.config.ts:3` defaults to port `4173`.
- `apps/dsa-web/playwright.config.ts:7` sets `fullyParallel: false`, so one
  Playwright invocation does not parallelize all specs.
- `apps/dsa-web/playwright.config.ts:10-14` starts build plus preview and reuses
  an existing server locally.
- `apps/dsa-web/playwright.config.ts:17` binds the test `baseURL` to that same
  port.
- `apps/dsa-web/e2e/fixtures/appSmoke.ts:998-1056` installs a context-level
  clipboard/EventSource/mock API harness.
- `apps/dsa-web/e2e/fixtures/appSmoke.ts:1056-1440`,
  `apps/dsa-web/e2e/fixtures/adminAuth.ts:602-620`, and
  `apps/dsa-web/e2e/fixtures/productAuth.ts:283-298` install broad API route
  handlers.

The main risk is not Playwright's intra-run parallelism. The risk is launching
multiple Playwright commands at once with the same default preview port, or
reusing an old local server whose build does not match the current checkout.

Use a unique port per concurrent attempt and keep workers bounded:

```bash
DSA_WEB_PLAYWRIGHT_PORT=4179 npm --prefix apps/dsa-web run test:e2e -- 'e2e/home-chart-browser.smoke.spec.ts' --project=chromium --workers=1
```

For a second concurrent attempt, use a different port:

```bash
DSA_WEB_PLAYWRIGHT_PORT=4180 npm --prefix apps/dsa-web run test:e2e -- 'e2e/home-fundamentals-summary.spec.ts' --project=chromium --workers=1
```

When the goal is to avoid reusing a stale local preview server, use a checked
free port and, if acceptable for the prompt, CI-style no-reuse behavior:

```bash
CI=1 DSA_WEB_PLAYWRIGHT_PORT=4179 npm --prefix apps/dsa-web run test:e2e -- 'e2e/home-chart-browser.smoke.spec.ts' --project=chromium --workers=1
```

Do not run two Playwright commands on the same `DSA_WEB_PLAYWRIGHT_PORT`.

## Home `act(...)` warning risk after T-1013/T-1020

Home risk appears mostly contained relative to Backtest.

Evidence:

- `HomeSurfacePage.test.tsx:81-87` has a local `flushPendingUiWork()` helper
  that wraps pending microtasks and dynamic imports in `act`.
- store-driven task updates are explicitly wrapped in `act` at
  `HomeSurfacePage.test.tsx:3277-3295`,
  `HomeSurfacePage.test.tsx:3685-3695`,
  `HomeSurfacePage.test.tsx:3767-3836`, and
  `HomeSurfacePage.test.tsx:3864-3885`.
- recent Home chart and fundamentals smoke specs are browser-level and do not
  share the Backtest unit-test mock pattern.

Residual risk:

- `HomeSurfacePage.test.tsx` is still a very large file with many async paths.
  New Home tests should keep using `act` for store mutations and
  `waitFor`/`findBy*` for UI hydration.
- This audit did not find a current Home warning source comparable to the
  Backtest warnings observed during the Backtest combination runs.

## Safer validation command templates

### Focused Vitest file

```bash
npm --prefix apps/dsa-web run test -- 'src/pages/__tests__/HomeSurfacePage.test.tsx' --reporter=dot
```

### Focused Vitest test name

```bash
npm --prefix apps/dsa-web run test -- 'src/pages/__tests__/BacktestPage.test.tsx' -t 'loads executable catalog templates without showing the unsupported warning' --reporter=dot
```

### Backtest combination, normal file parallelism

Use this to reproduce the real combined command surface:

```bash
npm --prefix apps/dsa-web run test -- 'src/pages/__tests__/BacktestPage.test.tsx' 'src/pages/__tests__/BacktestPage.lazy.test.tsx' 'src/pages/__tests__/DeterministicBacktestResultPage.test.tsx' 'src/pages/tests/DeterministicBacktestResultPage.test.tsx' --reporter=dot
```

Audit observation: passed `61/61`, but emitted Backtest `act(...)` warnings.

### Backtest combination, Vitest-native serial file execution

Use this when checking for file-order sensitivity without Jest-only flags:

```bash
npm --prefix apps/dsa-web run test -- 'src/pages/__tests__/BacktestPage.test.tsx' 'src/pages/__tests__/BacktestPage.lazy.test.tsx' 'src/pages/__tests__/DeterministicBacktestResultPage.test.tsx' 'src/pages/tests/DeterministicBacktestResultPage.test.tsx' --no-file-parallelism --reporter=dot
```

Audit observation: passed `61/61`, but emitted Backtest `act(...)` warnings.

### E2E single spec with isolated preview port

```bash
DSA_WEB_PLAYWRIGHT_PORT=4179 npm --prefix apps/dsa-web run test:e2e -- 'e2e/home-chart-browser.smoke.spec.ts' --project=chromium --workers=1
```

### E2E concurrent attempt on a different port

```bash
DSA_WEB_PLAYWRIGHT_PORT=4180 npm --prefix apps/dsa-web run test:e2e -- 'e2e/home-fundamentals-summary.spec.ts' --project=chromium --workers=1
```

### Docs-only validation for future audit artifacts

```bash
git diff --check -- 'docs/codex/audits/<audit-file>.md' && ./scripts/release_secret_scan.sh && git status --short --branch
```

## Recommended future tasks

### 1. Tests-only: Backtest Vitest reliability hardening

Recommended write type: tests-only.

Scope:

- `apps/dsa-web/src/pages/__tests__/BacktestPage.test.tsx`
- `apps/dsa-web/src/pages/__tests__/BacktestPage.lazy.test.tsx`
- `apps/dsa-web/src/pages/__tests__/DeterministicBacktestResultPage.test.tsx`
- `apps/dsa-web/src/pages/tests/DeterministicBacktestResultPage.test.tsx`

Goals:

- replace broad `vi.clearAllMocks()` reliance with explicit implementation
  reset/default setup;
- ensure import gates always release/reset even on failing assertions;
- wrap Backtest fireEvent paths that trigger async Drawer/page updates;
- keep lazy unresolved-promise coverage isolated;
- preserve Backtest calculation/runtime semantics.

Validation:

```bash
npm --prefix apps/dsa-web run test -- 'src/pages/__tests__/BacktestPage.test.tsx' 'src/pages/__tests__/BacktestPage.lazy.test.tsx' 'src/pages/__tests__/DeterministicBacktestResultPage.test.tsx' 'src/pages/tests/DeterministicBacktestResultPage.test.tsx' --reporter=dot
npm --prefix apps/dsa-web run test -- 'src/pages/__tests__/BacktestPage.test.tsx' 'src/pages/__tests__/BacktestPage.lazy.test.tsx' 'src/pages/__tests__/DeterministicBacktestResultPage.test.tsx' 'src/pages/tests/DeterministicBacktestResultPage.test.tsx' --no-file-parallelism --reporter=dot
```

### 2. Docs-only: frontend validation command template update

Recommended write type: docs-only.

Scope:

- `docs/frontend/validation-playbook.md` or the Codex prompt template docs that
  own frontend validation examples.

Goals:

- document quoted Vitest filters for zsh;
- replace any `--runInBand` examples with `--no-file-parallelism`;
- document Playwright `DSA_WEB_PLAYWRIGHT_PORT` isolation for parallel attempts;
- call out package-root filter paths when using `npm --prefix apps/dsa-web`.

Validation:

```bash
git diff --check -- '<changed-doc-file>' && ./scripts/release_secret_scan.sh
```

## Not recommended

- Script/package changes in the next step: useful later, but not required until
  docs and tests-only hardening prove the remaining friction.
- Playwright config changes: the current config is workable if future prompts
  avoid same-port concurrent runs and stale-server reuse.
- Source changes: no source root cause was established by this audit.

## Final classification

Prompt/command mistakes:

- unquoted zsh filters/globs;
- Jest-only `--runInBand`;
- root-relative filters passed through `npm --prefix`;
- same-port parallel Playwright attempts.

Actual flake or reliability risks:

- Backtest `act(...)` warnings observed in passing combined runs;
- stateful mock implementation queues around `vi.clearAllMocks()`;
- hoisted dynamic import gates in deterministic Backtest result tests;
- unresolved lazy chunk mock that must remain file-isolated.

Current best next write:

- tests-only for Backtest reliability.

Optional second write:

- docs-only for validation command templates.
