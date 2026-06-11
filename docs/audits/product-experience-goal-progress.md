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

None recorded yet.

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
