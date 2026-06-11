# Product Experience Goal Progress

Date: 2026-06-11
Branch: `codex/goal-product-experience-unification`
Mode: route-by-route private-beta product coherence work.

## Goal

Make WolfyStock feel like one coherent private-beta product instead of
disconnected feature pages, while preserving protected runtime boundaries.

Success criteria:

- Main consumer routes use consistent IA, cautious wording, evidence display,
  loading/empty/error handling, and mobile behavior.
- Admin/operator routes clearly separate operational diagnostics from consumer
  language.
- Labels for read-only, advisory-only, dry-run, no-send, no-live-quota,
  no-provider-blocking, fixture/demo, stale/fallback, insufficient evidence,
  and not-investment-advice are consistent across touched UI and docs.
- Consumer routes do not expose raw diagnostics, internal reason codes, stack
  traces, backend field names, provider/admin leakage, or overconfident trading
  advice.
- Each touched route/component has validation evidence.

## Protected Boundaries

This goal does not approve or enable:

- Public launch.
- Live quota enforcement, reservation consume/blocking, or route blocking.
- Provider runtime enforcement, provider order/fallback/cache changes, or
  provider blocking.
- Global MFA, auth/session/RBAC runtime changes.
- DB migration, cleanup, restore, or PITR execution.
- Broker/order/trade paths.
- External notification sending.

If a product improvement requires one of these areas, record it as a follow-up
proposal here and continue on frontend-safe work.

## Current Shared Surfaces

These files are the current highest-leverage unification points:

- `apps/dsa-web/src/utils/trustDisclosure.ts`: shared consumer trust chips for
  confidence, fallback, stale, partial, proxy, observe-only, blocked, and
  no-advice states.
- `apps/dsa-web/src/utils/evidenceDisplay.ts`: normalizes mixed evidence
  metadata into consumer/admin summaries and hides raw/debug/schema/trace text
  from consumer labels.
- `apps/dsa-web/src/utils/userFacingDataIssues.ts`: maps backend/internal
  issue codes into consumer-safe data availability messages.
- `apps/dsa-web/src/components/common/ConsumerEvidenceCoverageStrip.tsx` and
  `apps/dsa-web/src/components/common/ConsumerEvidencePacketStrip.tsx`: shared
  Home/report evidence strips.
- `apps/dsa-web/src/App.tsx`: canonical route gate for guest, protected, and
  admin surfaces.

Existing product safety policy anchors:

- `docs/audits/trading-no-advice-product-policy.md`
- `docs/audits/data-quality-user-disclosure-policy.md`

## Route Inventory

| Route family | Routes | Current pass status | Notes |
| --- | --- | --- | --- |
| Home / Guest | `/`, `/guest` | In review | Uses shared evidence strips and report no-advice copy; inspect for consistency with global labels. |
| Market Overview | `/market-overview` | In review | Has extensive data-trust tests; avoid provider/runtime changes. |
| Scanner | `/scanner` | In review | Existing scanner recovery work protects no-candidate and raw diagnostics leakage; inspect wording alignment. |
| Watchlist | `/watchlist` | In review | Protected route; inspect trust disclosure and portfolio/scanner handoff wording. |
| Portfolio | `/portfolio` | In review | Protected route; prioritize read-only/demo/manual-state labels and empty state. |
| Backtest | `/backtest`, `/backtest/results/:runId`, `/backtest/compare` | In review | Keep historical/simulated language separate from live trade readiness. |
| Options | `/options-lab` | In review | Preserve no-advice and demo/fixture boundaries. |
| Liquidity | `/market/liquidity-monitor` | In review | Keep macro/liquidity observations non-actionable. |
| Rotation | `/market/rotation-radar` | In review | Keep theme/candidate labels observation-only. |
| Auth | `/login`, `/register`, `/reset-password` | In review | Keep guest/admin/protected route wording coherent. |
| Admin/operator | `/settings/system`, `/admin/*` | In review | Operator diagnostics may expose technical terms only inside admin-scoped affordances. |

## First Findings

1. Shared consumer labels are close but not complete for the goal vocabulary.
   For example, `trustDisclosure.ts` has `observe-only`, `blocked`, and
   `non-advice`, while `evidenceDisplay.ts` maps dry-run/fixture/mock/synthetic
   to `演示数据`. The goal also needs consistent read-only, advisory-only,
   no-send, no-live-quota, and no-provider-blocking labels.

2. Admin/operator pages already use some explicit operational fields such as
   read-only and diagnostic-only, but labels are page-local in places. The
   safest first admin improvement is a shared operator boundary label set or a
   small local consolidation that does not change provider/runtime behavior.

3. Existing tests already enforce major consumer leakage boundaries on Market
   Overview, Watchlist, Options, Liquidity, Rotation, Backtest, and raw leakage
   helpers. New work should extend those guards instead of inventing a separate
   scan.

4. Route gates in `App.tsx` already separate public-safe, protected, and admin
   surfaces. Product coherence work should preserve those runtime decisions and
   only improve copy/labels/states around the gates.

## Planned Checkpoints

- `checkpoint(product): audit experience gaps`
  - This document plus initial route/shared-surface inventory.
- `checkpoint(product): unify consumer safety surfaces`
  - Shared consumer label normalization and targeted route/component tests.
- `checkpoint(product): unify admin operator surfaces`
  - Admin/operator boundary labeling for read-only/dry-run/no-send/no-live
    states, with page tests.
- `checkpoint(product): add route smoke evidence`
  - Bounded Playwright smoke or route evidence for touched surfaces.
- `feat(product): unify private beta experience`
  - Final integration after route-by-route deltas and validation.

## Validation Plan

Always run:

```bash
git diff --check
./scripts/release_secret_scan.sh --local-only
```

When frontend is touched:

```bash
cd apps/dsa-web
npm run typecheck
npm run build
```

Use focused Vitest commands for changed files, for example:

```bash
cd apps/dsa-web
npm run test -- src/utils/__tests__/evidenceDisplay.test.ts src/test-utils/__tests__/consumerRawLeakageGuard.test.ts
```

Use bounded Playwright smoke after route-impacting changes. Candidate specs:

- `consumer-copy-forbidden-vocabulary.smoke.spec.ts`
- `critical-route-launch-smoke.spec.ts`
- `market-overview-scanner.smoke.spec.ts`
- `public-safety-ai-scanner-options.smoke.spec.ts`
- `portfolio-launch-surface.spec.ts`
- `admin-ops-launch-surfaces.spec.ts`

## Follow-Up Proposals Requiring Approval

- Backtest support export API payload projection: if downloaded JSON/CSV
  artifacts themselves must be consumer-safe, add a read-only projection helper
  and tests. Approval needed because that changes the support artifact
  contract.

## Non-Approval Follow-Ups

- Consumer raw-leakage smoke coverage: extend
  `consumer-copy-forbidden-vocabulary.smoke.spec.ts` to include Backtest,
  Options, and auth routes with mocked fixtures. This is test-only, but it
  should be done carefully because those routes currently depend on separate
  specialized smoke fixtures.

## Checkpoint Log

### 2026-06-11 - audit experience gaps

- Created the route inventory and shared-surface map.
- Started read-only parallel audits for consumer, advanced/research,
  admin/operator, and validation coverage lanes.
- No runtime behavior, backend behavior, provider behavior, auth/session/RBAC,
  DB, broker/order, quota enforcement, or notification sending changed.

### 2026-06-11 - unify consumer safety surfaces

- Extended `trustDisclosure.ts` with stable private-beta boundary buckets for
  read-only, advisory-only, dry-run, no-send, no-live-quota,
  no-provider-blocking, fixture/demo, and no-advice states.
- Kept consumer-visible labels generic where the backend term is operational:
  `no-live-quota` resolves to `保持观察边界`,
  `no-provider-blocking` resolves to `不改变数据通路`, and
  `noExternalCalls=true` resolves to `不触发外部动作`.
- Added a bounded allowlist for the new private-beta term mappings so unrelated
  `advisory`, quota, provider, or runtime words are not surfaced by substring
  accident.
- Extended `evidenceDisplay.ts` tests and added `trustDisclosure.test.ts` to
  lock these mappings and prevent raw boundary terms such as
  `read_only_projection`, `quota_dry_run`, `liveEnforcement=false`,
  `wouldBlockCall=false`, and `synthetic_or_fixture_data_not_decision_grade`
  from appearing in consumer labels.

Validation:

```bash
npm --prefix apps/dsa-web run test -- src/utils/__tests__/trustDisclosure.test.ts src/utils/__tests__/evidenceDisplay.test.ts
npm --prefix apps/dsa-web run typecheck
npm --prefix apps/dsa-web run build
git diff --check
./scripts/release_secret_scan.sh --local-only
```

Result: all commands completed successfully. Vite build still reports the
pre-existing large chunk warning.

Boundary confirmation:

- No public launch approval.
- No live quota enforcement, reservation consume/blocking, or route blocking.
- No provider runtime enforcement, provider order/fallback/cache changes, or
  provider blocking.
- No auth/session/RBAC runtime changes.
- No DB migration, cleanup, restore, or PITR execution.
- No broker/order/trade paths.
- No external notification sending.

### 2026-06-11 - unify admin operator surfaces

- Updated `AdminNotificationsPage` so unknown delivery failures use a stable
  operator-facing summary instead of rendering backend diagnostics as normal
  notice bullets.
- Added `diagnosticDetails` to the local notice model. Raw delivery messages
  and structured diagnostics are available only inside the existing
  `notification-notice-raw-diagnostics` disclosure, which remains collapsed by
  default.
- Added regression tests that prove unknown diagnostics are absent from the
  default DOM for both transient test-send failures and persisted channel
  failure summaries. Transient diagnostics become visible only after the
  operator opens the disclosure.

Validation:

```bash
npm --prefix apps/dsa-web run test -- src/pages/__tests__/AdminNotificationsPage.test.tsx
npm --prefix apps/dsa-web run typecheck
npm --prefix apps/dsa-web run build
git diff --check
./scripts/release_secret_scan.sh --local-only
```

Result: all commands completed successfully. Vite build still reports the
pre-existing large chunk warning.

Boundary confirmation:

- Admin/operator copy only; no notification send path was executed outside the
  existing mocked frontend test.
- No public launch approval.
- No live quota enforcement, reservation consume/blocking, or route blocking.
- No provider runtime enforcement, provider order/fallback/cache changes, or
  provider blocking.
- No auth/session/RBAC runtime changes.
- No DB migration, cleanup, restore, or PITR execution.
- No broker/order/trade paths.
- No external notification sending.

### 2026-06-11 - add route smoke evidence

- Removed default-visible Backtest copy that named broker/order paths. The
  research boundary now says historical rule labels do not trigger external
  execution or mutate portfolio holdings.
- Kept Market Provider Operations product-surface setup gaps highlighted but
  collapsed by default, so admin first screens stay summary-first and full
  diagnostics remain operator-initiated.
- Updated bounded Playwright route smoke expectations to the current safer
  product IA: Market Overview accepts the shared no-trade/no-order boundary,
  Portfolio and Watchlist empty states use private-beta research-first wording,
  Settings uses the consumer-facing `账户中心` h1, and admin ops tests assert the
  current Chinese operator labels.

Route smoke evidence:

```bash
npm --prefix apps/dsa-web run test -- src/pages/__tests__/BacktestPage.test.tsx -t "defaults to the point-and-shoot normal workspace"
npm --prefix apps/dsa-web run test -- src/pages/__tests__/MarketProviderOperationsPage.test.tsx
DSA_WEB_PLAYWRIGHT_PORT=4174 npm --prefix apps/dsa-web run test:e2e -- consumer-copy-regression.smoke.spec.ts secondary-consumer-copy.smoke.spec.ts
WOLFYSTOCK_ADMIN_OPS_ROUTE_FILTER=logs,cost,evidence,market-providers,provider-circuits DSA_WEB_PLAYWRIGHT_PORT=4175 npm --prefix apps/dsa-web run test:e2e -- admin-ops-launch-surfaces.spec.ts
CI=1 DSA_WEB_PLAYWRIGHT_PORT=4187 npm --prefix apps/dsa-web run test:e2e -- semantic-route-headings.spec.ts --project=chromium --reporter=list
```

Result: all route smoke commands completed successfully after the bounded
copy/IA fixes above. Playwright generated failure screenshots/videos/traces
during earlier red runs; they remain local test artifacts and are not part of
the branch diff.

Additional validation for this checkpoint:

```bash
npm --prefix apps/dsa-web run typecheck
npm --prefix apps/dsa-web run build
git diff --check
./scripts/release_secret_scan.sh --local-only
```

Boundary confirmation:

- Frontend copy, tests, and smoke expectations only.
- No public launch approval.
- No live quota enforcement, reservation consume/blocking, or route blocking.
- No provider runtime enforcement, provider order/fallback/cache changes, or
  provider blocking.
- No auth/session/RBAC runtime changes.
- No DB migration, cleanup, restore, or PITR execution.
- No broker/order/trade paths enabled; Backtest copy now avoids default-visible
  broker/order route language.
- No external notification sending.

### 2026-06-11 - sanitize Liquidity reason fallbacks

- Replaced Liquidity consumer fallback labels for unknown coverage diagnostics,
  evidence reasons, degradation reasons, pillars, directions, and evidence keys
  with stable Chinese private-beta copy instead of title-casing backend reason
  codes.
- Added a Liquidity page regression test with unmapped backend-style reason
  values to prove default consumer DOM does not show snake_case codes or their
  title-cased variants.
- Re-ran the Liquidity degraded Playwright smoke at desktop and mobile
  viewports to validate the page still renders the consumer-safe unavailable
  state.

Validation:

```bash
npm --prefix apps/dsa-web run test -- src/pages/__tests__/LiquidityMonitorPage.test.tsx
DSA_WEB_PLAYWRIGHT_PORT=4178 npm --prefix apps/dsa-web run test:e2e -- market-liquidity-monitor-degraded.spec.ts --project=chromium --workers=1
```

Result: all commands completed successfully. The Playwright web server still
reports the pre-existing Vite large chunk warning.

Boundary confirmation:

- Frontend display labels and tests only.
- No public launch approval.
- No live quota enforcement, reservation consume/blocking, or route blocking.
- No provider runtime enforcement, provider order/fallback/cache changes, or
  provider blocking.
- No auth/session/RBAC runtime changes.
- No DB migration, cleanup, restore, or PITR execution.
- No broker/order/trade paths.
- No external notification sending.

### 2026-06-11 - sanitize Admin Logs default rows

- Added admin-only default label helpers for event names, event types, source
  dimensions, route references, request references, and trace references.
- Updated Admin Logs health summary, operator issue rollups, data-missing rows,
  and default desktop/mobile business queues so raw event/type codes,
  route/endpoint paths, request IDs, and trace IDs stay out of default visible
  rows.
- Kept detail drawers, raw logs, copy affordances, cleanup previews, and API
  contracts unchanged.

Validation:

```bash
npm --prefix apps/dsa-web run test -- src/pages/__tests__/AdminLogsPage.test.tsx
WOLFYSTOCK_ADMIN_OPS_ROUTE_FILTER=logs DSA_WEB_PLAYWRIGHT_PORT=4188 npm --prefix apps/dsa-web run test:e2e -- admin-ops-launch-surfaces.spec.ts --project=chromium --workers=1
```

Result: all commands completed successfully. The first Playwright retry failed
at web-server startup because `shortIdentifier` became unused after removing
default trace IDs; `npm --prefix apps/dsa-web run typecheck` exposed the TS6133
root cause, and the unused helper was removed before the successful smoke.

Boundary confirmation:

- Frontend display labels and tests only.
- No public launch approval.
- No live quota enforcement, reservation consume/blocking, or route blocking.
- No provider runtime enforcement, provider order/fallback/cache changes, or
  provider blocking.
- No auth/session/RBAC runtime changes.
- No DB migration, cleanup, restore, or PITR execution.
- No broker/order/trade paths.
- No external notification sending.

### 2026-06-11 - sanitize Backtest support disclosure labels

- Replaced Backtest support/OOS preview labels for diagnostic-only,
  decision-grade, provider-call, engine-math, optimizer, parameter-sweep, and
  strategy-parameter flags with safe support labels instead of backend field
  names.
- Added generic labels for unknown boolean support safeguards and unknown
  availability reasons so `payload`, `diagnosticOnly`, `decisionGrade`,
  `provider_calls_executed`, `engine_math_changed`, and similar internal keys
  do not render in the disclosure.
- Preserved existing support export loading/downloading behavior and did not
  change backend artifacts or API contracts.

Validation:

```bash
npm --prefix apps/dsa-web run test -- src/components/backtest/__tests__/BacktestSupportExportsDisclosure.test.tsx
DSA_WEB_PLAYWRIGHT_PORT=4189 npm --prefix apps/dsa-web run test:e2e -- backtest-visual-result.smoke.spec.ts --project=chromium --workers=1
```

Result: all commands completed successfully. The Playwright web server still
reports the pre-existing Vite large chunk warning.

Boundary confirmation:

- Frontend display labels and tests only.
- No public launch approval.
- No live quota enforcement, reservation consume/blocking, or route blocking.
- No provider runtime enforcement, provider order/fallback/cache changes, or
  provider blocking.
- No auth/session/RBAC runtime changes.
- No DB migration, cleanup, restore, or PITR execution.
- No broker/order/trade paths or order execution behavior.
- No external notification sending.

### 2026-06-11 - final integration summary

Final checkpoint commits on the branch:

- `a77dd7da checkpoint(product): audit experience gaps`
- `88093684 checkpoint(product): unify consumer safety surfaces`
- `e37f8029 checkpoint(product): unify admin operator surfaces`
- `cb93eee5 checkpoint(product): add route smoke evidence`
- `0685f045 fix(product): sanitize liquidity reason labels`
- `0c5bfaaf fix(product): sanitize operator diagnostics labels`
- `51f06a5f fix(product): sanitize backtest and admin links`
- `c5807b59 fix(product): sanitize backtest assumption labels`

Routes and surfaces reviewed or changed:

- Consumer/shared safety: `trustDisclosure.ts`, `evidenceDisplay.ts`, and
  route smoke expectations for Home, Market Overview, Scanner, Watchlist,
  Portfolio, Settings/auth shell headings, Liquidity, Rotation, Options, and
  Backtest.
- Liquidity: unknown coverage/evidence reason fallbacks now use generic
  consumer copy.
- Backtest: default workspace copy, support disclosure labels, result CSV
  reason labels, warning labels, compare labels, and shared assumption list
  fallbacks now avoid raw backend fields and execution/trade advice.
- Admin/operator: Notifications, Admin Logs, Market Provider Operations, and
  admin route smoke expectations now keep diagnostics behind operator
  affordances and avoid raw default-row leakage.

Final validation evidence accumulated:

```bash
npm --prefix apps/dsa-web run test -- src/utils/__tests__/trustDisclosure.test.ts src/utils/__tests__/evidenceDisplay.test.ts
npm --prefix apps/dsa-web run test -- src/pages/__tests__/AdminNotificationsPage.test.tsx
npm --prefix apps/dsa-web run test -- src/pages/__tests__/BacktestPage.test.tsx -t "defaults to the point-and-shoot normal workspace"
npm --prefix apps/dsa-web run test -- src/pages/__tests__/MarketProviderOperationsPage.test.tsx
npm --prefix apps/dsa-web run test -- src/pages/__tests__/LiquidityMonitorPage.test.tsx
npm --prefix apps/dsa-web run test -- src/pages/__tests__/AdminLogsPage.test.tsx
npm --prefix apps/dsa-web run test -- src/components/backtest/__tests__/BacktestSupportExportsDisclosure.test.tsx
npm --prefix apps/dsa-web run test -- src/pages/__tests__/RuleBacktestComparePage.test.tsx
npm --prefix apps/dsa-web run test -- src/components/backtest/__tests__/BacktestResultReport.test.tsx
npm --prefix apps/dsa-web run test -- src/components/backtest/__tests__/DeterministicBacktestResultView.test.tsx
npm --prefix apps/dsa-web run typecheck
npm --prefix apps/dsa-web run build
DSA_WEB_PLAYWRIGHT_PORT=4174 npm --prefix apps/dsa-web run test:e2e -- consumer-copy-regression.smoke.spec.ts secondary-consumer-copy.smoke.spec.ts
WOLFYSTOCK_ADMIN_OPS_ROUTE_FILTER=logs,cost,evidence,market-providers,provider-circuits DSA_WEB_PLAYWRIGHT_PORT=4175 npm --prefix apps/dsa-web run test:e2e -- admin-ops-launch-surfaces.spec.ts
CI=1 DSA_WEB_PLAYWRIGHT_PORT=4187 npm --prefix apps/dsa-web run test:e2e -- semantic-route-headings.spec.ts --project=chromium --reporter=list
DSA_WEB_PLAYWRIGHT_PORT=4178 npm --prefix apps/dsa-web run test:e2e -- market-liquidity-monitor-degraded.spec.ts --project=chromium --workers=1
WOLFYSTOCK_ADMIN_OPS_ROUTE_FILTER=logs DSA_WEB_PLAYWRIGHT_PORT=4188 npm --prefix apps/dsa-web run test:e2e -- admin-ops-launch-surfaces.spec.ts --project=chromium --workers=1
DSA_WEB_PLAYWRIGHT_PORT=4189 npm --prefix apps/dsa-web run test:e2e -- backtest-visual-result.smoke.spec.ts --project=chromium --workers=1
WOLFYSTOCK_ADMIN_OPS_ROUTE_FILTER=market-providers DSA_WEB_PLAYWRIGHT_PORT=4190 npm --prefix apps/dsa-web run test:e2e -- admin-ops-launch-surfaces.spec.ts --project=chromium --workers=1
DSA_WEB_PLAYWRIGHT_PORT=4191 npm --prefix apps/dsa-web run test:e2e -- backtest-visual-result.smoke.spec.ts --project=chromium --workers=1
DSA_WEB_PLAYWRIGHT_PORT=4192 npm --prefix apps/dsa-web run test:e2e -- backtest-visual-result.smoke.spec.ts --project=chromium --workers=1
git diff --check
./scripts/release_secret_scan.sh --local-only
```

Known validation notes:

- Vite build consistently reports the pre-existing large chunk warning.
- Earlier red retries were resolved before commit: one Backtest page broad
  test exposed unrelated existing result-heading expectations, one Playwright
  retry exposed an unused `shortIdentifier`, and one Market Provider test
  selected the wrong duplicate Admin Logs link.

Remaining inconsistent surfaces:

- Downloaded Backtest support artifact payloads can still contain raw contract
  fields by design; changing those payloads requires approval because it alters
  the support export contract.
- `consumer-copy-forbidden-vocabulary.smoke.spec.ts` still does not directly
  include Backtest, Options, and auth routes; those routes are covered by
  specialized route smoke today.

Final boundary confirmation:

- Public launch remains not approved.
- Live quota enforcement, reservation consume/blocking, and route blocking
  remain not enabled.
- Provider runtime enforcement, provider order/fallback/cache changes, and
  provider blocking remain unchanged.
- Global MFA and auth/session/RBAC runtime behavior remain unchanged.
- DB migration, cleanup, restore, and PITR execution remain untouched.
- Broker/order/trade paths remain untouched.
- External notification sending remains disabled/not executed.

### 2026-06-11 - sanitize Backtest assumption list fallbacks

- Updated shared Backtest `AssumptionList` rendering so known assumption keys
  keep translated labels, unknown non-internal keys use a generic execution
  assumption label, and unknown internal-looking keys are skipped.
- Sanitized assumption values so objects, arrays containing internal-looking
  text, trace/stack/payload-like values, and provider/authority/contract
  tokens render as safe review copy rather than backend field names.
- Added a focused Deterministic Backtest view test that proves
  `provider_calls_executed`, `authorityScope`, `contractKind`,
  `diagnosticOnly`, `decisionGrade`, `payload`, `trace`, and `stack` do not
  leak while the known `entry_fill_timing` label remains useful.

Validation:

```bash
npm --prefix apps/dsa-web run test -- src/components/backtest/__tests__/DeterministicBacktestResultView.test.tsx
npm --prefix apps/dsa-web run typecheck
npm --prefix apps/dsa-web run build
DSA_WEB_PLAYWRIGHT_PORT=4192 npm --prefix apps/dsa-web run test:e2e -- backtest-visual-result.smoke.spec.ts --project=chromium --workers=1
git diff --check
./scripts/release_secret_scan.sh --local-only
```

Result: command completed successfully. A worker also ran ESLint for the two
touched files and reported exit 0. The Playwright web server still reports the
pre-existing Vite large chunk warning.

Boundary confirmation:

- Frontend display labels and tests only.
- No public launch approval.
- No live quota enforcement, reservation consume/blocking, or route blocking.
- No provider runtime enforcement, provider order/fallback/cache changes, or
  provider blocking.
- No auth/session/RBAC runtime changes.
- No DB migration, cleanup, restore, or PITR execution.
- No broker/order/trade paths or order execution behavior.
- No external notification sending.

### 2026-06-11 - sanitize admin drill-through and Backtest exports

- Sanitized Market Provider Operations Admin Logs drill-through hrefs so raw
  `provider`, `source`, `trace`, token, and secret-like parameters are not
  emitted as standalone query keys. Safe search terms are merged into the
  allowlisted `query` parameter and IDs are reduced to safe code characters.
- Updated Backtest result CSV export rows so trade reason fields reuse safe
  labels and unknown internal-looking reason tokens become redacted research
  labels instead of raw backend codes.
- Updated Backtest result warning text so unknown internal-looking warning
  codes/messages are shown as generic support-safe copy.
- Updated Backtest compare metric and sensitivity labels so unknown
  internal-looking fields render as `比较字段需复核` instead of title-casing
  backend keys.

Validation:

```bash
npm --prefix apps/dsa-web run test -- src/pages/__tests__/MarketProviderOperationsPage.test.tsx
npm --prefix apps/dsa-web run test -- src/pages/__tests__/RuleBacktestComparePage.test.tsx
npm --prefix apps/dsa-web run test -- src/components/backtest/__tests__/BacktestResultReport.test.tsx
npm --prefix apps/dsa-web run typecheck
npm --prefix apps/dsa-web run build
WOLFYSTOCK_ADMIN_OPS_ROUTE_FILTER=market-providers DSA_WEB_PLAYWRIGHT_PORT=4190 npm --prefix apps/dsa-web run test:e2e -- admin-ops-launch-surfaces.spec.ts --project=chromium --workers=1
DSA_WEB_PLAYWRIGHT_PORT=4191 npm --prefix apps/dsa-web run test:e2e -- backtest-visual-result.smoke.spec.ts --project=chromium --workers=1
```

Result: all commands completed successfully. The first
MarketProviderOperations test retry failed because the assertion selected the
shared drill-through strip instead of the local sanitized Admin Logs link; the
selector was narrowed to all `/zh/admin/logs` hrefs before the successful run.
The Playwright web server still reports the pre-existing Vite large chunk
warning.

Boundary confirmation:

- Frontend link construction, display labels, local CSV text, and tests only.
- No public launch approval.
- No live quota enforcement, reservation consume/blocking, or route blocking.
- No provider runtime enforcement, provider order/fallback/cache changes, or
  provider blocking.
- No auth/session/RBAC runtime changes.
- No DB migration, cleanup, restore, or PITR execution.
- No broker/order/trade paths or order execution behavior.
- No external notification sending.
