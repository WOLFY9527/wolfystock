# T-1175 WolfyStock Public Beta Candidate Progress

Status: RUNNING

Date: 2026-06-08
Workspace: `/Users/yehengli/worktrees/t1175-public-beta-candidate`
Branch: `codex/t1175-public-beta-candidate`
Base commit: `829249b2`

## Goal

Move WolfyStock toward a To-C public beta candidate where a first-time user
sees a finance research product rather than an AI demo or terminal prototype.

Target readiness:

- Public Beta Readiness: at least 85/100.
- P0 blockers: 0.
- No real deployment, production secret exposure, destructive DB operation,
  broker/trading action, provider runtime/order/cache/API/auth/RBAC/scoring
  semantic weakening, or consumer raw diagnostics leakage.

## Required Inputs Read

- `AGENTS.md`
- `docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md`
- `docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md`
- `docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md`
- `docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md`
- `docs/data-reliability/provider-source-confidence-contract.md`
- `docs/data-reliability/evidence-readiness-matrix.md`
- `docs/frontend/WOLFYSTOCK_CONSUMER_DATA_QUALITY_UX.md`
- `docs/frontend/README.md`
- `docs/frontend/visual-system.md`
- `docs/frontend/validation-playbook.md`
- `docs/audits/public-launch-gap-register.md`

## Boundary Decision

This goal may improve public-beta maturity through page/component copy,
consumer-safe layout hierarchy, tests, and release evidence. It must not open
protected backend/runtime domains unless a later scoped task explicitly names
the allowed files and semantic delta.

Allowed current write families:

- `docs/codex/goals/T-1175_PROGRESS.md`
- Consumer UI/page/component/test files under `apps/dsa-web/` when changes are
  presentation-only and preserve API/auth/provider/cache/scoring semantics.
- Focused docs or tests that lock current public-beta boundaries.

Protected domains kept closed:

- Provider runtime order, live-call paths, fallback behavior, MarketCache TTL,
  SWR, cold-start behavior, cache keys, and payload meaning.
- `sourceAuthorityAllowed`, `scoreContributionAllowed`, `authorityGrant`, score
  contribution, ranking, filtering, scanner selection, and market scoring
  semantics.
- Auth/RBAC/security behavior and API response contract changes.
- Portfolio accounting, broker sync/import, cash, holdings, P&L, FX, cost basis,
  and all trading or order actions.
- DB migrations, production DB reads/writes, destructive cleanup, real
  notification/payment/quota writes, and real deployment.

## Baseline V0

Method: static repository/doc scan before fresh browser evidence.

Public Beta Readiness estimate: 58/100.

Scorecard estimate:

| Area | Points | V0 |
| --- | ---: | ---: |
| guest/auth/protected | 15 | 9 |
| Market/Liquidity/Rotation observation-mode | 15 | 8 |
| demo research loop | 20 | 11 |
| consumer UI de-AI/de-diagnostic | 15 | 8 |
| perceived speed/partial/last-good | 10 | 6 |
| admin health | 10 | 6 |
| deploy precheck | 15 | 10 |

Baseline blocker inventory:

- P0 candidate: first-fold route evidence is not yet proven at desktop and
  mobile for the core consumer journey.
- P0 candidate: Market/Liquidity/Rotation usefulness is still constrained by
  data qualification/authority boundaries; safe partial observation must remain
  consumer-language only.
- P0 candidate: release candidate precheck is not yet freshly validated in this
  branch.
- P1: public launch register still records full public multi-user launch as
  NO-GO; T-1175 can only move toward a bounded public beta candidate, not real
  production launch.
- P1: route-level raw diagnostic and no-advice checks need fresh proof for the
  requested journey.

## Checkpoint 1 - Frontend Safety Fixes

Time: 2026-06-08 03:10 CST.

Public Beta Readiness estimate after focused unit/build validation: 70/100.

Scorecard estimate:

| Area | Points | V0 | CP1 |
| --- | ---: | ---: | ---: |
| guest/auth/protected | 15 | 9 | 12 |
| Market/Liquidity/Rotation observation-mode | 15 | 8 | 10 |
| demo research loop | 20 | 11 | 12 |
| consumer UI de-AI/de-diagnostic | 15 | 8 | 12 |
| perceived speed/partial/last-good | 10 | 6 | 6 |
| admin health | 10 | 6 | 8 |
| deploy precheck | 15 | 10 | 10 |

P0/P1 movement:

- P0 narrowed: protected route overlay now preserves the current localized path
  in `redirect`; login/register success now consumes that safe redirect instead
  of always returning home.
- P0 narrowed: Market Overview fallback and old adapter payload wording no longer
  presents "demo/interface/sample" narrative on default consumer surfaces.
- P0 narrowed: Admin Market Providers no longer renders provider endpoint values
  in L3 detail or L4 JSON summaries.
- P1 remains: full route-level Playwright proof at desktop/mobile is still
  pending for the broader journey.
- P1 remains: public launch docs still keep real public multi-user launch as
  NO-GO; this remains a bounded beta-candidate hardening branch only.
- P1 remains: performance sidecar identified Rotation/Liquidity retained
  last-good behavior as a safe later frontend-only opportunity; not opened in
  this checkpoint to avoid widening state-machine scope.

Route before/after:

| Route | Before | After | Evidence |
| --- | --- | --- | --- |
| guest protected overlay | Login CTA opened bare login route and lost source | CTA opens localized login with redirect to current protected route | `AuthGuardOverlay.test.tsx` |
| login/register | Success always navigated home | Success navigates to safe `redirect` when present | `LoginPage.test.tsx` |
| `/zh/market-overview` | fallback copy could read as interface/demo sample | fallback and legacy payload copy reads as data-insufficient observation | `MarketOverviewPage.test.tsx`, `market.test.ts` |
| `/zh/admin/market-providers` | selected provider detail and L4 JSON exposed endpoint | visible detail shows redacted reference only; L4 JSON omits endpoint | `MarketProviderOperationsPage.test.tsx` |

Validation completed:

- `npm --prefix apps/dsa-web run test -- src/components/auth/__tests__/AuthGuardOverlay.test.tsx src/pages/__tests__/LoginPage.test.tsx src/pages/__tests__/MarketProviderOperationsPage.test.tsx src/api/__tests__/market.test.ts src/pages/__tests__/MarketOverviewPage.test.tsx --run` -> PASS, 5 files / 138 tests.
- `npm --prefix apps/dsa-web run lint` -> PASS.
- `npm --prefix apps/dsa-web run build` -> PASS; Vite emitted existing large-chunk warnings.
- `npm --prefix apps/dsa-web run check:design` -> PASS with existing warning-only `Shell.tsx` native-ui finding.
- `git diff --check` -> PASS.
- `./scripts/release_secret_scan.sh` -> PASS.

Validation pending:

- Focused Playwright at `1440x1000` and `390x844` for guest/login/market/admin
  routes.
- P1 focused backend/release tests around admin/provider/auth/release contracts.
- Broader consumer journey routes: liquidity, rotation, scanner, watchlist,
  portfolio, report/history.

Rollback:

- Revert checkpoint commit after it is created:
  `git revert <checkpoint-1-commit>`.
- Restore changed frontend files to the baseline checkpoint:
  `git restore --source=050e2276 -- apps/dsa-web/src/api/__tests__/market.test.ts apps/dsa-web/src/api/market.ts apps/dsa-web/src/components/auth/AuthGuardOverlay.tsx apps/dsa-web/src/components/auth/__tests__/AuthGuardOverlay.test.tsx apps/dsa-web/src/pages/LoginPage.tsx apps/dsa-web/src/pages/MarketOverviewPage.tsx apps/dsa-web/src/pages/MarketProviderOperationsPage.tsx apps/dsa-web/src/pages/__tests__/LoginPage.test.tsx apps/dsa-web/src/pages/__tests__/MarketOverviewPage.test.tsx apps/dsa-web/src/pages/__tests__/MarketProviderOperationsPage.test.tsx`.

## Milestone Plan

1. Baseline checkpoint and score.
2. Consumer-safe first-fold maturity for Market Overview, Liquidity Monitor,
   Rotation Radar, and the guest/auth journey.
3. Demo research loop and protected-route journey proof without buy/sell/order
   advice.
4. Admin health readiness proof with raw payloads closed by default.
5. Release precheck: secret scan, focused backend/Vitest, lint, build,
   design guard, and Playwright proof at `1440x1000` and `390x844`.

## Validation Plan

Baseline checkpoint:

- `git diff --check -- docs/codex/goals/T-1175_PROGRESS.md`
- `./scripts/release_secret_scan.sh`
- `git status --short --branch`

Implementation checkpoint:

- `git diff --check`
- `./scripts/release_secret_scan.sh`
- Focused backend tests around touched domains, if any.
- Focused Vitest for touched pages/adapters/components.
- `npm --prefix apps/dsa-web run lint`
- `npm --prefix apps/dsa-web run build`
- `npm --prefix apps/dsa-web run check:design`
- Focused Playwright routes at `1440x1000` and `390x844`:
  guest, login/register, market overview, liquidity, rotation, scanner,
  watchlist, portfolio, report/history, and admin health.

## Checkpoint 2 - Launch Smoke Truth Alignment

Time: 2026-06-08 04:07 CST.

Public Beta Readiness estimate after focused Playwright validation: 76/100.

Scorecard estimate:

| Area | Points | V0 | CP1 | CP2 |
| --- | ---: | ---: | ---: | ---: |
| guest/auth/protected | 15 | 9 | 12 | 13 |
| Market/Liquidity/Rotation observation-mode | 15 | 8 | 10 | 11 |
| demo research loop | 20 | 11 | 12 | 13 |
| consumer UI de-AI/de-diagnostic | 15 | 8 | 12 | 13 |
| perceived speed/partial/last-good | 10 | 6 | 6 | 6 |
| admin health | 10 | 6 | 8 | 9 |
| deploy precheck | 15 | 10 | 10 | 11 |

P0/P1 movement:

- P0 narrowed: core public/admin route smoke now runs at `1440x1000` and
  `390x844` for home, Market Overview, Rotation Radar, Scanner, backtest,
  cost observability, provider diagnostics, system settings, and admin user
  portfolio projection.
- P0 narrowed: no-secret smoke now runs through home, Market Overview, Options
  Lab, Portfolio, cost observability, and provider diagnostics without raw
  secret/debug/provider payload leakage. Options Lab keeps negative safety copy
  such as "不会提交订单" while still blocking executable trading/action wording.
- P0 narrowed: admin auth harness now verifies full admin, cost-only admin,
  providers-only admin, denied admin, legacy fallback-disabled, and missing
  capability-field paths with current route copy and no protected API fetches
  when capability gates deny access.
- P1 improved: provider diagnostics L2 event/quota/probe panels now keep full
  mobile grid width and desktop three-column layout, so the expanded diagnostic
  group is visible and scrollable at `390x844` without changing data or
  provider semantics.
- P1 improved: restored the shared product auth e2e harness utility so product
  smoke specs execute route assertions instead of failing at static import time.

Route before/after:

| Route | Before | After | Evidence |
| --- | --- | --- | --- |
| `/zh/admin/provider-circuits` | L2 event/quota/probe panels could collapse into hidden grid cells on mobile; tests still asserted stale Provider wording | L2 panels span mobile width; smoke asserts current Chinese copy and collapsed/expanded redaction behavior | `AdminProviderCircuitDiagnosticsPage.test.tsx`, `critical-route-launch-smoke.spec.ts`, `no-secret-critical-surface.smoke.spec.ts`, `admin-auth-harness.spec.ts` |
| `/zh/settings/system` | smoke expected hidden root wrapper to be visible | smoke now asserts attached root plus visible `系统设置` and health summary | `critical-route-launch-smoke.spec.ts`, `admin-auth-harness.spec.ts` |
| `/zh/options-lab` | no-secret smoke could fail on negative safety copy containing order words | smoke now blocks executable trading/action wording while allowing explicit no-order boundary copy | `no-secret-critical-surface.smoke.spec.ts` |
| product protected routes | `productAuth.ts` fixture could not resolve shared product auth harness | restored `src/test-utils/productAuthHarness.ts` and no-secret product smoke reaches page assertions | `no-secret-critical-surface.smoke.spec.ts` |

Validation completed:

- `npm --prefix apps/dsa-web run test -- --run src/pages/__tests__/AdminProviderCircuitDiagnosticsPage.test.tsx` -> PASS, 1 file / 8 tests.
- `DSA_WEB_PLAYWRIGHT_PORT=4177 npm --prefix apps/dsa-web run test:e2e -- e2e/critical-route-launch-smoke.spec.ts` -> PASS, 8 tests.
- `DSA_WEB_PLAYWRIGHT_PORT=4180 npm --prefix apps/dsa-web run test:e2e -- e2e/admin-auth-harness.spec.ts` -> PASS, 7 tests.
- `DSA_WEB_PLAYWRIGHT_PORT=4181 npm --prefix apps/dsa-web run test:e2e -- e2e/no-secret-critical-surface.smoke.spec.ts` -> PASS, 6 tests.
- `git diff --check` -> PASS.

Validation pending:

- P1 focused backend/release tests around admin/provider/auth/release contracts.
- Full `npm --prefix apps/dsa-web run lint`, build, and `check:design` after
  the final validation batch.
- Broader consumer journey routes: liquidity, watchlist, portfolio/report
  history beyond current no-secret and critical-route coverage.

Rollback:

- Revert checkpoint commit after it is created:
  `git revert <checkpoint-2-commit>`.
- Restore changed smoke/layout/test utility files to checkpoint 1:
  `git restore --source=50e61289 -- apps/dsa-web/e2e/admin-auth-harness.spec.ts apps/dsa-web/e2e/critical-route-launch-smoke.spec.ts apps/dsa-web/e2e/no-secret-critical-surface.smoke.spec.ts apps/dsa-web/src/pages/AdminProviderCircuitDiagnosticsPage.tsx apps/dsa-web/src/test-utils/productAuthHarness.ts`.

## Checkpoints

| Time | Commit | Scope | Validation |
| --- | --- | --- | --- |
| 2026-06-08 02:30 CST | `050e2276` | Initial baseline progress doc | `git diff --check`, `./scripts/release_secret_scan.sh` |
| 2026-06-08 03:10 CST | this checkpoint commit | Auth redirect, Market Overview consumer fallback copy, Provider Ops endpoint redaction | Focused Vitest, lint, build, check:design, `git diff --check`, `./scripts/release_secret_scan.sh` |
| 2026-06-08 04:07 CST | this checkpoint commit | Playwright truth alignment, provider diagnostics mobile L2 layout, product auth e2e harness restore | AdminProviderCircuit unit test, critical route smoke, admin auth smoke, no-secret smoke, `git diff --check` |

## Running Notes

- Subagents are being used for read-only product, market/backend, frontend UX,
  auth/journey, admin/ops, and DB/safety scans. Main agent owns all writes,
  integration, validation, commits, and pushes.
- Product, market/backend, auth/journey, admin/ops, DB/safety, performance, and
  QA/release sidecars have completed read-only scans. Frontend UX was closed
  before returning a result, so main-agent UI checks use the repository frontend
  guardrails and focused browser/tests instead.
