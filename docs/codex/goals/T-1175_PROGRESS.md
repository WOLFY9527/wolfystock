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
  secret/debug/provider payload leakage. The initial checkpoint still allowed
  explicit negative no-order copy; CP4 later tightened default Options Lab copy
  to avoid order/broker vocabulary on consumer surfaces.
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

- Full `npm --prefix apps/dsa-web run lint`, build, and `check:design` after
  the final validation batch.
- Broader consumer journey routes: liquidity, watchlist, portfolio/report
  history beyond current no-secret and critical-route coverage.

Rollback:

- Revert checkpoint commit after it is created:
  `git revert <checkpoint-2-commit>`.
- Restore changed smoke/layout/test utility files to checkpoint 1:
  `git restore --source=50e61289 -- apps/dsa-web/e2e/admin-auth-harness.spec.ts apps/dsa-web/e2e/critical-route-launch-smoke.spec.ts apps/dsa-web/e2e/no-secret-critical-surface.smoke.spec.ts apps/dsa-web/src/pages/AdminProviderCircuitDiagnosticsPage.tsx apps/dsa-web/src/test-utils/productAuthHarness.ts`.

## Checkpoint 3 - Release Contract Inventory Repair

Time: 2026-06-08 04:22 CST.

Public Beta Readiness estimate after backend/release validation: 81/100.

P0/P1 movement:

- P0 narrowed: focused admin/provider/auth/release pytest gate now passes with
  current route inventory.
- P1 improved: backend route capability fixture now covers authenticated-user
  portfolio scenario-risk and user-alerts routes without changing their auth
  dependency or promoting them to admin capability surfaces.
- P1 improved: frontend auth paywall inventory sentinel now tracks current
  Chinese/English overlay copy instead of stale launch wording.

Validation completed:

- `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_auth_route_capability_inventory.py::test_backend_route_capability_inventory_covers_current_dependency_guarded_routes tests/test_auth_route_capability_inventory.py::test_frontend_guest_paywall_and_admin_gate_boundaries_are_represented_in_existing_tests -q` -> PASS, 2 tests.
- `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/api/test_market_provider_operations.py tests/api/test_admin_provider_circuit_diagnostics.py tests/api/test_auth_rbac_release_contracts.py tests/test_auth_route_capability_inventory.py tests/test_release_secret_scan.py tests/api/test_auth_security_hardening.py` -> PASS, 88 tests.
- `./scripts/release_secret_scan.sh` -> PASS.
- `npm --prefix apps/dsa-web run lint` -> PASS.
- `npm --prefix apps/dsa-web run build` -> PASS; existing Vite large-chunk warnings remain.
- `npm --prefix apps/dsa-web run check:design` -> PASS with existing warning-only `Shell.tsx` native-ui finding.
- `git diff --check` -> PASS.

Validation note:

- The first pytest attempt used the default `/Users/yehengli/.browser-use-env/bin/python` and failed before collection because that environment has no `pytest`.
- A second attempt with Python 3.11 used a stale path `tests/test_auth_security_hardening.py`; the current file is `tests/api/test_auth_security_hardening.py`.

Validation pending:

- Broader consumer journey routes: liquidity, watchlist, portfolio/report
  history beyond current no-secret and critical-route coverage.

Rollback:

- Revert checkpoint commit after it is created:
  `git revert <checkpoint-3-commit>`.
- Restore changed inventory files to checkpoint 2:
  `git restore --source=8effe763 -- tests/fixtures/auth/backend_route_capability_inventory.json tests/test_auth_route_capability_inventory.py`.

## Checkpoint 4 - Consumer Journey Proof And Options Copy Tightening

Time: 2026-06-08 04:57 CST.

Public Beta Readiness estimate after broader consumer journey validation:
85/100.

Scorecard estimate:

| Area | Points | V0 | CP1 | CP2 | CP3 | CP4 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| guest/auth/protected | 15 | 9 | 12 | 13 | 13 | 13 |
| Market/Liquidity/Rotation observation-mode | 15 | 8 | 10 | 11 | 11 | 13 |
| demo research loop | 20 | 11 | 12 | 13 | 13 | 16 |
| consumer UI de-AI/de-diagnostic | 15 | 8 | 12 | 13 | 13 | 14 |
| perceived speed/partial/last-good | 10 | 6 | 6 | 6 | 6 | 7 |
| admin health | 10 | 6 | 8 | 9 | 9 | 9 |
| deploy precheck | 15 | 10 | 10 | 11 | 14 | 13 |

P0/P1/P2 movement:

- P0 cleared for this branch target: broad consumer route smoke now passes at
  desktop and mobile for Home, Market Overview, Liquidity Monitor, Rotation
  Radar, Scanner, Watchlist, Portfolio, Options Lab, market research IA, and
  Backtest result launch surfaces.
- P1 improved: Options Lab default safety copy no longer uses visible
  order/broker wording such as `下单`, `订单`, or `经纪商`; it now says
  `不构成执行指令`, `不会触发外部执行`, and `不连接外部执行通道`.
- P1 improved: consumer copy regression smoke now matches the intentional
  Market Overview boundary where `market-intelligence-actionability-strip` is
  absent by default and the visible page uses decision semantics plus chart
  evidence instead of diagnostic actionability strips.
- P1 improved: Portfolio scenario-risk smoke now asserts translated bounded
  labels and explicitly rejects raw snake_case tokens such as
  `theme_mapping_pending` and `scenario_coverage_incomplete`.
- P2 remains: public launch register still keeps real public multi-user launch
  as NO-GO; this branch is a bounded beta-candidate readiness branch, not a
  production deployment.
- P2 remains: Vite still emits existing large-chunk warnings during e2e/build;
  no bundle-splitting change was opened in this checkpoint.

Route before/after:

| Route | Before | After | Evidence |
| --- | --- | --- | --- |
| `/zh/options-lab` | Default safety copy still contained negative order/broker wording | Default copy uses execution-boundary language without order/broker terms; payoff/math/API semantics unchanged | `OptionsLabPage.test.tsx`, `consumer-copy-regression.smoke.spec.ts`, `public-safety-ai-scanner-options.smoke.spec.ts`, `research-surfaces-launch.spec.ts` |
| `/zh/market-overview` | Broad consumer copy smoke expected the removed actionability diagnostic strip | Smoke now locks the default diagnostic strip absence and verifies decision semantics plus visual evidence | `consumer-copy-regression.smoke.spec.ts`, `market-research-surfaces.spec.ts` |
| `/zh/market/liquidity-monitor` | Broad consumer copy smoke expected stale exact degraded text | Smoke now accepts current bounded observation copy while still blocking raw diagnostics | `consumer-copy-regression.smoke.spec.ts`, `market-liquidity-monitor-degraded.spec.ts` |
| `/zh/portfolio` | Scenario-risk smoke expected raw snake_case warning tokens | Smoke now requires translated product labels and rejects snake_case leakage | `portfolio-launch-surface.spec.ts` |
| `/zh/backtest/results/34` | Research smoke expected old bento test IDs and developer-detail controls | Smoke now verifies current hero/KPI/result-summary/evidence/ledger disclosure structure | `research-surfaces-launch.spec.ts` |

Validation completed:

- `npm --prefix apps/dsa-web run test -- --run src/pages/__tests__/OptionsLabPage.test.tsx` -> PASS, 1 file / 39 tests.
- `DSA_WEB_PLAYWRIGHT_PORT=4198 npm --prefix apps/dsa-web run test:e2e -- e2e/consumer-copy-regression.smoke.spec.ts e2e/portfolio-launch-surface.spec.ts e2e/research-surfaces-launch.spec.ts e2e/public-safety-ai-scanner-options.smoke.spec.ts e2e/market-liquidity-monitor-degraded.spec.ts e2e/watchlist-user-alerts.smoke.spec.ts e2e/market-research-surfaces.spec.ts` -> PASS, 32 tests.
- `git diff --check` -> PASS.
- `./scripts/release_secret_scan.sh` -> PASS.
- `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/api/test_market_provider_operations.py tests/api/test_admin_provider_circuit_diagnostics.py tests/api/test_auth_rbac_release_contracts.py tests/test_auth_route_capability_inventory.py tests/test_release_secret_scan.py tests/api/test_auth_security_hardening.py` -> PASS, 88 tests.
- `npm --prefix apps/dsa-web run lint` -> PASS.
- `npm --prefix apps/dsa-web run build` -> PASS; existing Vite large-chunk warnings remain.
- `npm --prefix apps/dsa-web run check:design` -> PASS with existing warning-only `Shell.tsx` native-ui finding.

Rollback:

- Revert checkpoint commit after it is created:
  `git revert <checkpoint-4-commit>`.
- Restore changed files to checkpoint 3:
  `git restore --source=5784eb2a -- apps/dsa-web/src/pages/OptionsLabPage.tsx apps/dsa-web/src/pages/__tests__/OptionsLabPage.test.tsx apps/dsa-web/e2e/consumer-copy-regression.smoke.spec.ts apps/dsa-web/e2e/controlled-user-testing.smoke.spec.ts apps/dsa-web/e2e/portfolio-launch-surface.spec.ts apps/dsa-web/e2e/public-safety-ai-scanner-options.smoke.spec.ts apps/dsa-web/e2e/readiness-browser-acceptance.smoke.spec.ts apps/dsa-web/e2e/research-surfaces-launch.spec.ts apps/dsa-web/e2e/secondary-consumer-copy.smoke.spec.ts docs/codex/goals/T-1175_PROGRESS.md`.

## Checkpoints

| Time | Commit | Scope | Validation |
| --- | --- | --- | --- |
| 2026-06-08 02:30 CST | `050e2276` | Initial baseline progress doc | `git diff --check`, `./scripts/release_secret_scan.sh` |
| 2026-06-08 03:10 CST | `50e61289` | Auth redirect, Market Overview consumer fallback copy, Provider Ops endpoint redaction | Focused Vitest, lint, build, check:design, `git diff --check`, `./scripts/release_secret_scan.sh` |
| 2026-06-08 04:07 CST | `8effe763` | Playwright truth alignment, provider diagnostics mobile L2 layout, product auth e2e harness restore | AdminProviderCircuit unit test, critical route smoke, admin auth smoke, no-secret smoke, `git diff --check` |
| 2026-06-08 04:22 CST | `5784eb2a` | Backend auth route inventory and paywall copy sentinel repair | Focused backend/release pytest, release secret scan, lint, build, check:design, `git diff --check` |
| 2026-06-08 04:57 CST | `06dfba6a` | Consumer journey proof, Options Lab execution-boundary copy, stale e2e truth alignment | Options Lab Vitest, 32-test consumer Playwright batch, focused backend pytest, release secret scan, lint, build, check:design, `git diff --check` |

## Running Notes

- Subagents are being used for read-only product, market/backend, frontend UX,
  auth/journey, admin/ops, and DB/safety scans. Main agent owns all writes,
  integration, validation, commits, and pushes.
- Product, market/backend, auth/journey, admin/ops, DB/safety, performance, and
  QA/release sidecars have completed read-only scans. Frontend UX was closed
  before returning a result, so main-agent UI checks use the repository frontend
  guardrails and focused browser/tests instead.
