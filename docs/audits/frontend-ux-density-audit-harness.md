# Frontend UX Density Audit Harness

Date: 2026-05-09

## Purpose

`apps/dsa-web/e2e/ux-density-audit.spec.ts` is a local Playwright harness for
reviewing first-viewport overload before launch-facing UI changes are accepted.
It does not make density numbers CI-blocking by default; it records them as
structured metrics so reviewers can compare route shape over time.

The harness is intended to answer:

- how many card-like surfaces are visible in the first viewport;
- how many buttons, inputs, selects, textareas, and button-like controls are
  visible;
- whether debug/provider/raw/fallback/mock terms are visible;
- whether glossary or help affordances are present;
- what users encounter first in the viewport content order;
- whether horizontal overflow, console errors, page errors, or secret-like raw
  text appear.

## Routes Covered

- `/zh`
- `/zh/chat`
- `/zh/scanner`
- `/zh/watchlist`
- `/zh/market-overview`
- `/zh/market/rotation-radar`
- `/options-lab`
- `/zh/backtest/results/34`
- `/zh/portfolio`
- `/zh/admin/logs`
- `/zh/admin/cost-observability`
- `/zh/admin/evidence-workflow`
- `/zh/admin/market-providers`
- `/zh/admin/provider-circuits`

Each route runs at desktop `1440x1000` and mobile `390x844` viewports.

## Running Locally

Use an isolated Playwright preview port so existing local servers are not
reused or killed:

```bash
cd apps/dsa-web
DSA_WEB_PLAYWRIGHT_PORT=<free-port> npx playwright test e2e/ux-density-audit.spec.ts --project=chromium
```

By default, the JSON report is written to:

```text
apps/dsa-web/test-results/ux-density-audit-report.json
```

To write somewhere else:

```bash
UX_DENSITY_AUDIT_OUTPUT=/tmp/wolfystock-ux-density-audit.json \
DSA_WEB_PLAYWRIGHT_PORT=<free-port> \
npx playwright test e2e/ux-density-audit.spec.ts --project=chromium
```

The report path is intentionally a test output or temporary path and should not
be committed.

## Report Schema

The current schema version is `wolfystock_ux_density_audit_v1`.

Per route and viewport, the report records:

- `viewport`
- `finalUrl`
- `approximateVisibleCardCount`
- `visibleButtonInputCount`
- `debugProviderRawTermHits`
- `glossaryHelpAffordanceCount`
- `horizontalOverflow`
- `consolePageErrors`
- `firstMeaningfulHeadingText`
- `firstViewportContentOrder`

The card count is approximate by design. It uses semantic article-like nodes,
test IDs containing card/panel/summary, and rounded surface classes as a
review heuristic, not as a product contract.

## Assertions

Only hard safety checks fail the test:

- no horizontal overflow;
- no console or page errors;
- no visible raw secret-like content such as bearer tokens, API-key assignments,
  password assignments, cookie assignments, or token assignments.

Card count, control count, raw-term hits, glossary/help affordance count, first
heading, and first viewport content order are emitted as review metrics only.

## Harness Boundaries

The harness reuses existing Playwright route fixtures where available and adds
small local mocks only for audit-only admin endpoints that did not already have
fixture coverage. It does not call live providers, mutate backend state, change
production page code, or wire this audit into launch acceptance.

No package script was added because the current `apps/dsa-web/package.json`
only has the generic `test:e2e` script and no established audit-specific e2e
script pattern.
