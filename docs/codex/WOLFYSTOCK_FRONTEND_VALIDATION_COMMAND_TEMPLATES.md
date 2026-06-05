# WolfyStock Frontend Validation Command Templates

Purpose: copy-paste-safe frontend validation commands for Codex prompts and
manual local runs.

Scope:

- `npm --prefix apps/dsa-web run test` uses `vitest run`
- `npm --prefix apps/dsa-web run test:e2e` uses `playwright test`
- examples below avoid the command mistakes captured in T-1028

## Vitest package-root rule

When using `npm --prefix apps/dsa-web`, all file filters must be relative to
`apps/dsa-web`.

Use:

```bash
npm --prefix apps/dsa-web run test -- 'src/pages/__tests__/HomeSurfacePage.test.tsx' --reporter=dot
```

Do not use:

```bash
npm --prefix apps/dsa-web run test -- apps/dsa-web/src/pages/__tests__/HomeSurfacePage.test.tsx
```

## Vitest shell-safe file filters

Quote file paths or globs after `--` so zsh does not expand them before Vitest
starts.

Single file:

```bash
npm --prefix apps/dsa-web run test -- 'src/pages/__tests__/BacktestPage.test.tsx' --reporter=dot
```

Multiple files:

```bash
npm --prefix apps/dsa-web run test -- 'src/pages/__tests__/BacktestPage.test.tsx' 'src/pages/__tests__/BacktestPage.lazy.test.tsx' 'src/pages/__tests__/DeterministicBacktestResultPage.test.tsx' 'src/pages/tests/DeterministicBacktestResultPage.test.tsx' --reporter=dot
```

Quoted glob:

```bash
npm --prefix apps/dsa-web run test -- 'src/pages/**/__tests__/*.test.tsx' --reporter=dot
```

## Vitest serial file execution

Use Vitest-native serial file execution when needed:

```bash
npm --prefix apps/dsa-web run test -- 'src/pages/__tests__/BacktestPage.test.tsx' 'src/pages/__tests__/BacktestPage.lazy.test.tsx' 'src/pages/__tests__/DeterministicBacktestResultPage.test.tsx' 'src/pages/tests/DeterministicBacktestResultPage.test.tsx' --no-file-parallelism --reporter=dot
```

Do not use Jest-style `--runInBand`. This repo's Vitest version does not
support it.

## Playwright single-run template

Use a unique `DSA_WEB_PLAYWRIGHT_PORT` and keep the invocation single-worker:

```bash
DSA_WEB_PLAYWRIGHT_PORT=4179 npm --prefix apps/dsa-web run test:e2e -- 'e2e/home-chart-browser.smoke.spec.ts' --project=chromium --workers=1
```

Another example:

```bash
DSA_WEB_PLAYWRIGHT_PORT=4180 npm --prefix apps/dsa-web run test:e2e -- 'e2e/home-fundamentals-summary.spec.ts' --project=chromium --workers=1
```

## Playwright concurrency warning

If two Playwright runs must happen at the same time, give each run a different
`DSA_WEB_PLAYWRIGHT_PORT`.

Use:

```bash
DSA_WEB_PLAYWRIGHT_PORT=4179 npm --prefix apps/dsa-web run test:e2e -- 'e2e/home-chart-browser.smoke.spec.ts' --project=chromium --workers=1
DSA_WEB_PLAYWRIGHT_PORT=4180 npm --prefix apps/dsa-web run test:e2e -- 'e2e/home-fundamentals-summary.spec.ts' --project=chromium --workers=1
```

Do not run two Playwright invocations on the same `DSA_WEB_PLAYWRIGHT_PORT`.
