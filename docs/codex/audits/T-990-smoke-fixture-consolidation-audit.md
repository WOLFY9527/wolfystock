# T-990 Smoke fixture consolidation audit

Task: T-990 Smoke fixture consolidation audit

Mode: READ-ONLY-AUDIT with one explicitly allowed audit artifact.

Allowed artifact: `docs/codex/audits/T-990-smoke-fixture-consolidation-audit.md`

Observed HEAD during audit: `4d435916` (`T-988: harden Scanner Home React paths`)

Scope boundary:

- No product source changes.
- No test behavior changes.
- No fixture/helper/config changes in this task.

## Executive summary

The three current smoke specs are worth keeping, but their setup has crossed the
line from healthy repetition into fixture debt. The duplication is concentrated
in four places:

1. signed-in auth route stubs;
2. Home/Scanner evidence payload builders and route handlers;
3. consumer-safe and no-overflow assertions;
4. Options and Market mock route fragments that already overlap with nearby
   shared e2e harnesses.

The safest next write is not a broad e2e framework pass. It is a narrow test-only
consolidation that extracts small shared builders and assertion helpers while
leaving route-specific payload meaning inside each spec. Over-extraction would
hide the exact surface each smoke test is protecting, especially the focused
Home/Scanner evidence assertions and the broad controlled-user journey.

## Audit basis

Files inspected:

- `apps/dsa-web/e2e/controlled-user-testing.smoke.spec.ts`
- `apps/dsa-web/e2e/consumer-copy-regression.smoke.spec.ts`
- `apps/dsa-web/e2e/home-scanner-evidence-browser.smoke.spec.ts`
- `apps/dsa-web/e2e/fixtures/appSmoke.ts`
- `apps/dsa-web/e2e/fixtures/authenticatedRouteSmoke.ts`
- `apps/dsa-web/e2e/fixtures/productAuth.ts`
- `apps/dsa-web/e2e/fixtures/portfolioSmoke.ts`
- `apps/dsa-web/playwright.config.ts`
- `docs/codex/audits/T-987-post-wave-react-doctor-smoke-stability-audit.md`

Parallel scouting note:

- Four read-only subagents were requested for spec/helper scouting, but all four
  failed with upstream `503 Service Unavailable` before returning code findings.
- Main-agent local inspection completed the audit without delegated evidence.

## Current smoke intent to preserve

### `controlled-user-testing.smoke.spec.ts`

Intent must stay broad but meaningful:

- one Home research/evidence/provenance flow;
- one Market actionability/readiness flow;
- one Scanner top-down to candidate-evidence flow on narrow viewport;
- one Backtest deterministic research-report flow;
- one Options readiness/payoff/no-execution flow.

Evidence:

- route installers are split by surface at
  `controlled-user-testing.smoke.spec.ts:78`,
  `:464`,
  `:748`,
  `:1084`;
- the five smoke tests remain surface-driven at
  `controlled-user-testing.smoke.spec.ts:1127-1310`.

### `consumer-copy-regression.smoke.spec.ts`

Intent must stay desktop/mobile safety-oriented:

- two-viewport loop remains important at
  `consumer-copy-regression.smoke.spec.ts:5-8`,
  `:876-987`;
- copy checks cover Home, Market, Scanner, and Options safety wording with
  viewport-specific rendering expectations.

### `home-scanner-evidence-browser.smoke.spec.ts`

Intent must stay focused:

- only Home evidence strip/provenance and Scanner candidate evidence/workflow
  are exercised at `home-scanner-evidence-browser.smoke.spec.ts:611-697`;
- this spec is the most direct guard against provenance/evidence leakage and
  should not be blurred into a generic route-pack helper.

## Top duplicate areas

### 1. Signed-in auth/session setup is duplicated

Repeated route stubs:

- `controlled-user-testing.smoke.spec.ts:8-17`, `:32-47`
- `consumer-copy-regression.smoke.spec.ts:30-56`
- `consumer-copy-regression.smoke.spec.ts:82-107`
- `home-scanner-evidence-browser.smoke.spec.ts:13-22`, `:32-47`

Nearby shared helpers already exist:

- `authenticatedRouteSmoke.ts:75-141`
- `productAuth.ts:283-356`

Assessment:

- The three target specs are re-creating the same signed-in user and
  `auth/status` + `auth/me` responses instead of reusing one thin auth helper.
- `consumer-copy-regression` duplicates auth twice in the same file:
  `installSignedInSessionRoutes` and the auth prelude inside
  `installAuthenticatedHomeEvidenceRoutes`.

Safe extraction:

- shared `installSignedInAuthRoutes(page, options?)` helper for user auth only;
- shared `openSignedInRoute(page, path)` helper that waits for
  `domcontentloaded`.

Do not extract into:

- `page.context().route('**/api/v1/**')` catch-all style used by
  `appSmoke.ts:997-1457`;
- `unrouteAll` cleanup semantics from
  `authenticatedRouteSmoke.ts:124-129`.

Reason:

- these smoke specs rely on explicit per-endpoint overrides on top of
  `appSmoke`'s broad API harness;
- switching to a broader route owner would increase route precedence ambiguity
  and make teardown more dangerous.

### 2. Home evidence/provenance mock payloads are duplicated

Near-identical Home route installers:

- `controlled-user-testing.smoke.spec.ts:78-339`
- `consumer-copy-regression.smoke.spec.ts:82-230`
- `home-scanner-evidence-browser.smoke.spec.ts:49-280`

Repeated endpoints:

- `**/api/v1/stocks/*/evidence`
- `**/api/v1/stocks/ORCL/history`
- `**/api/v1/history/3` or `**/api/v1/history/3**`

Repeated payload fragments:

- ORCL evidence packet shell:
  `controlled-user-testing.smoke.spec.ts:81-100`,
  `consumer-copy-regression.smoke.spec.ts:109-128`,
  `home-scanner-evidence-browser.smoke.spec.ts:51-70`
- ORCL price history sample:
  `controlled-user-testing.smoke.spec.ts:68-76`, `:102-123`
  and inlined again at
  `consumer-copy-regression.smoke.spec.ts:130-157`,
  `home-scanner-evidence-browser.smoke.spec.ts:72-99`
- detailed history/report frame with evidence coverage and source provenance:
  `controlled-user-testing.smoke.spec.ts:125-339`,
  `consumer-copy-regression.smoke.spec.ts:159-230` plus following fields,
  `home-scanner-evidence-browser.smoke.spec.ts:101-278`

Safe extraction:

- one shared ORCL Home fixture builder module for:
  - signed-in Home evidence route installer;
  - reusable `homeHistoryData()`;
  - reusable base evidence/provenance payload fragments.

Must remain route-local:

- final assertions about which strip is expected on which page;
- text variants that intentionally differ between broad user smoke and stricter
  consumer-copy smoke, for example:
  - `operationAdvice: '数据不足，结论仅供观察。'` in
    `controlled-user-testing.smoke.spec.ts:141-147`
  - `operationAdvice: 'Wait for a controlled pullback before adding.'` in
    `consumer-copy-regression.smoke.spec.ts:175-181` and
    `home-scanner-evidence-browser.smoke.spec.ts:117-123`

Reason:

- the payload should be assembled from shared fragments, but each spec still
  needs to choose the exact consumer boundary wording it is proving.

### 3. Scanner evidence/context fixtures are duplicated

Repeated route families:

- `controlled-user-testing.smoke.spec.ts:471-763`
- `consumer-copy-regression.smoke.spec.ts:384-609`
- `home-scanner-evidence-browser.smoke.spec.ts:282-598`

Repeated endpoints:

- `**/api/v1/scanner/runs**`
- `**/api/v1/scanner/watchlists/recent**`
- `**/api/v1/scanner/runs/11` or `**/api/v1/scanner/runs/11**`

Repeated payload themes:

- run summary for `id: 11`, `theme_id`, `theme_label`, shortlist counts;
- NVDA candidate with `candidateEvidenceFrame` and provenance entries;
- top-down `scanner_context_frame`.

Existing nearby reuse signal:

- `appSmoke.ts` already owns generic scanner run/theme fixtures at
  `appSmoke.ts:10-241` and serves scanner APIs at `appSmoke.ts:1090-1116`.

Assessment:

- The target smoke specs are not reusing `appSmoke`'s scanner builders, but they
  also cannot simply defer to `appSmoke` wholesale because they need more
  evidence/provenance-rich payloads than the generic smoke harness provides.

Safe extraction:

- a shared builder file for scanner evidence/context test data:
  - base `runSummary`;
  - base NVDA candidate;
  - shared provenance entry fragments;
  - helper installers for the three scanner endpoints only.

Must remain route-local:

- whether a spec asserts `candidateEvidenceFrame`,
  `candidate_research_summary_frame`, or workflow ordering;
- whether mobile candidate summary IDs or inline evidence IDs are used;
- any summary text that expresses the surface contract differently across specs.

### 4. Consumer-safe wording and overflow checks are duplicated

Repeated wording guards:

- `controlled-user-testing.smoke.spec.ts:19-22`, `:55-66`
- `consumer-copy-regression.smoke.spec.ts:10-13`, `:58-76`
- `home-scanner-evidence-browser.smoke.spec.ts:9-11`, inline
  `not.toContainText(...)` assertions at `:634-643`, `:682-683`

Repeated overflow checks:

- `controlled-user-testing.smoke.spec.ts:49-53`
- `consumer-copy-regression.smoke.spec.ts:78-80`
- `home-scanner-evidence-browser.smoke.spec.ts:600-604`
- existing shared helper already exists at
  `authenticatedRouteSmoke.ts:67-69`
- existing product helper also exists at `productAuth.ts:358-360`

Assessment:

- overflow is the easiest safe extraction;
- wording checks are only partly safe to centralize because the regexes and
  sanitizer allowlists intentionally differ.

Safe extraction:

- reuse a single shared `expectNoHorizontalOverflow(page)` helper;
- extract a shared sanitizer/assert helper with parameters:
  - allowed compliance strings to strip;
  - forbidden internal regex;
  - forbidden trading regex.

Must remain local:

- the concrete forbidden regex presets for each smoke pack when their policy
  differs;
- route-level negative assertions on a specific strip or shell instead of the
  whole page.

Reason:

- a single global forbidden regex would likely either over-block benign research
  copy or under-block product-specific unsafe phrasing.

### 5. Options route mocks overlap with existing product-auth fixture

Duplicated Options builders:

- `controlled-user-testing.smoke.spec.ts:764-1125`
- `consumer-copy-regression.smoke.spec.ts:611-874`
- nearby shared helper in `productAuth.ts:43-332`

Repeated concepts:

- `optionsUnderlying`
- `optionsMetadata`
- `optionContract`
- `optionsSummary`
- `optionsExpirations`
- `optionsChain`
- strategy compare response
- decision response

Assessment:

- This is real duplication, but it is not the first extraction target for the
  T-990 follow-up because the current audit is scoped to the three named smoke
  specs and Home/Scanner evidence duplication is more acute.
- Still, any future consolidation pass should avoid creating a fourth parallel
  Options fixture layer.

Safe extraction:

- only if the future write task explicitly includes `productAuth.ts`, reuse or
  extend the existing product-auth options builders instead of inventing a new
  e2e-only options fixture file.

Stop condition:

- if Home/Scanner consolidation starts to pull in `productAuth.ts`, the write
  task should split. Mixing Home/Scanner fixture consolidation with Options
  harness refactoring is too broad.

## What must not be extracted

These items should remain in the route-level spec body or a route-local installer
because extracting them would hide the behavior under test:

1. Exact test assertions and test IDs for each route:
   - Home strips and chart assertions in
     `controlled-user-testing.smoke.spec.ts:1134-1155`
   - Market actionability/detail assertions in
     `consumer-copy-regression.smoke.spec.ts:910-929`
   - Scanner workflow-order assertion in
     `home-scanner-evidence-browser.smoke.spec.ts:684-686`

2. Route-specific payload semantics:
   - Home `researchReadiness`, `evidenceCoverageFrame`,
     `sourceProvenanceFrame`
   - Scanner `candidateEvidenceFrame`,
     `candidateSourceProvenanceFrame`,
     `scanner_context_frame`
   - Market `marketActionabilityFrame`,
     `marketIntelligenceEvidenceFrame`

3. Surface-specific consumer wording:
   - broad user-testing copy may be analytical but still more descriptive;
   - consumer-copy regression intentionally enforces stricter desktop/mobile
     safety language;
   - evidence-browser smoke intentionally focuses on leakage and provenance chips.

4. Viewport-specific rendering choices:
   - desktop vs mobile loop in `consumer-copy-regression`;
   - narrow Scanner route in `controlled-user-testing`;
   - per-viewport reruns in `home-scanner-evidence-browser`.

5. Teardown decisions around repeated `page.unroute(...)`:
   - these are currently explicit and endpoint-scoped at
     `home-scanner-evidence-browser.smoke.spec.ts:647-651`,
     `:690-694`;
   - replacing them with a generic cleanup helper that calls `unrouteAll` risks
     deleting `appSmoke`'s base catch-all routes.

## Flake and stability risks

### Risk 1. Over-broad route ownership can break `appSmoke`

`appSmoke` installs a context-level catch-all API router at
`appSmoke.ts:1055-1457`. The three target specs layer more specific page routes
on top. A future consolidation that switches specific installers to a generic
`page.context().route('**/api/v1/**')` owner would change route precedence and
make failures harder to localize.

Stop condition:

- if the refactor needs to replace endpoint-specific `page.route(...)` with a
  catch-all `**/api/v1/**` override, stop and split the task.

### Risk 2. Generic cleanup can remove base routes and reintroduce page reuse bugs

`authenticatedRouteSmoke.ts` cleans up with `page.unrouteAll({ behavior:
'ignoreErrors' })` at `authenticatedRouteSmoke.ts:124-129`. The focused evidence
spec instead uses endpoint-specific `page.unroute(...)` because it loops through
two viewports in one test and needs controlled override teardown.

If a shared helper starts calling `unrouteAll` inside these viewport loops, it
can remove `appSmoke`'s underlying routes and create later-request failures that
look like:

- `ERR_CONNECTION_REFUSED`
- unhandled API route failures
- blank root / guest redirects after first viewport pass

Stop condition:

- if helper cleanup needs `unrouteAll`, do not proceed inside the same task;
  redesign teardown to be endpoint-specific.

### Risk 3. Reusing one page across multiple viewport passes requires deterministic route reset

`home-scanner-evidence-browser` runs `for (const viewport of viewports)` within
each test and reuses the same `page`, then manually unroutes overrides before the
next viewport iteration:

- `home-scanner-evidence-browser.smoke.spec.ts:613-652`
- `home-scanner-evidence-browser.smoke.spec.ts:656-695`

This pattern is stable today because override scope is explicit. A consolidation
that hides install/uninstall order inside generic helpers can accidentally stack
duplicate handlers or leave stale handlers from the previous viewport.

### Risk 4. Broad webServer churn remains outside this refactor and should stay unchanged

Playwright uses:

- `npm run build && npm run preview`
- `reuseExistingServer: !process.env.CI`

at `playwright.config.ts:10-15`.

This refactor should not touch `playwright.config.ts`, server ownership, ports,
or server reuse. Otherwise the task would stop being a fixture consolidation and
would enter runtime-flake territory.

### Risk 5. Existing regex differences are policy differences, not pure duplication

The forbidden-word patterns differ materially:

- `controlled-user-testing.smoke.spec.ts:19-22`
- `consumer-copy-regression.smoke.spec.ts:10-13`
- `home-scanner-evidence-browser.smoke.spec.ts:9-11`

Collapsing them into one regex without preserving spec-specific intent could
weaken consumer-safety assertions or create false positives that produce brittle
tests.

## Recommended future write task

### Task shape

Minimal future write task: test-only consolidation of shared Playwright smoke
fixture fragments for auth, Home evidence, Scanner evidence/context, and common
assertions.

### Exact allowed files

Primary recommendation:

- `apps/dsa-web/e2e/controlled-user-testing.smoke.spec.ts`
- `apps/dsa-web/e2e/consumer-copy-regression.smoke.spec.ts`
- `apps/dsa-web/e2e/home-scanner-evidence-browser.smoke.spec.ts`
- `apps/dsa-web/e2e/fixtures/authenticatedRouteSmoke.ts`
- `apps/dsa-web/e2e/fixtures/smokeEvidence.ts` (new)

Optional only if required by implementation and explicitly authorized:

- `apps/dsa-web/e2e/fixtures/productAuth.ts`

Not recommended in the same task:

- `apps/dsa-web/e2e/fixtures/appSmoke.ts`
- `apps/dsa-web/playwright.config.ts`
- any app source files
- any non-target e2e specs

### Suggested extraction boundary

`smokeEvidence.ts` should contain only:

- shared signed-in user fixture builder or installer;
- `homeHistoryData()` and Home ORCL evidence/provenance fragment builders;
- Scanner NVDA evidence/context fragment builders;
- shared `expectNoHorizontalOverflow(page)`;
- parameterized consumer-safe text assertion helpers.

The spec files should still own:

- final route installers per surface;
- final route endpoint mapping;
- surface-specific copy overrides;
- final assertions and test flow.

## Validation commands for the future write task

Run exactly these focused commands after consolidation:

```bash
npm --prefix apps/dsa-web run test:e2e -- e2e/controlled-user-testing.smoke.spec.ts --project=chromium
npm --prefix apps/dsa-web run test:e2e -- e2e/consumer-copy-regression.smoke.spec.ts --project=chromium
npm --prefix apps/dsa-web run test:e2e -- e2e/home-scanner-evidence-browser.smoke.spec.ts --project=chromium
```

Then verify workspace hygiene:

```bash
git diff --check
git status --short --branch
```

Recommended extra diagnostics only if failures appear:

```bash
npm --prefix apps/dsa-web run test:e2e -- e2e/home-scanner-evidence-browser.smoke.spec.ts --project=chromium --repeat-each=3
npm --prefix apps/dsa-web run test:e2e -- e2e/consumer-copy-regression.smoke.spec.ts --project=chromium --repeat-each=3
```

## Stop conditions for the future write task

Stop and split the task if any of the following becomes necessary:

1. touching `appSmoke.ts` catch-all route ownership;
2. touching `playwright.config.ts`, `webServer`, ports, retries, or server reuse;
3. replacing endpoint-specific route cleanup with `unrouteAll`;
4. widening into generic Options harness refactoring via `productAuth.ts`;
5. changing product assertions, test IDs, route targets, viewport coverage, or
   copy expectations;
6. introducing a shared fixture layer that owns all surfaces through one
   monolithic mock router.

## Recommended implementation order

1. Extract shared overflow helper usage first.
2. Extract signed-in auth helper with no cleanup side effects.
3. Extract Home ORCL evidence/provenance fragment builders.
4. Extract Scanner NVDA evidence/context fragment builders.
5. Consolidate consumer-safe text assertion helper last, preserving per-spec
   regex presets.

This order keeps route ownership stable and makes it easier to isolate the first
flake if one appears.

## Final recommendation

The next write should be a narrow e2e-only consolidation, not a generic harness
rewrite. The best target is a new `smokeEvidence.ts` helper plus minimal edits to
the three named specs and, at most, `authenticatedRouteSmoke.ts`. Keep the broad
controlled-user smoke broad, keep consumer-copy dual-viewport, keep
Home/Scanner-evidence focused, and do not abstract away the exact route-specific
payload meaning those tests are supposed to protect.
