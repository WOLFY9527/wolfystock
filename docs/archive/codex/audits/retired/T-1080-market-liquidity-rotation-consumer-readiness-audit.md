# T-1080 Market Liquidity Rotation Consumer Readiness Audit

Task ID: T-1080-AUDIT

Task title: Market Liquidity Rotation consumer readiness audit

Mode: READ-ONLY-AUDIT with docs-only report artifact.

Date: 2026-06-07

Allowed artifact:

`docs/codex/audits/T-1080-market-liquidity-rotation-consumer-readiness-audit.md`

Observed workspace:

- cwd: `/Users/yehengli/worktrees/t1080-market-liquidity-rotation-consumer-readiness-audit`
- branch: `codex/t1080-market-liquidity-rotation-consumer-readiness-audit`
- base commit inspected before writing this report: `87254125`
- local branch status at preflight: clean, behind `origin/main` by 7 commits; no pull or branch switch was performed.

Scope boundary:

- Liquidity Monitor and Rotation Radar source, tests, e2e fixtures, and product docs were inspected only.
- This audit does not implement UI changes, browser fixtures, test repairs, API/schema changes, DTO changes,
  provider changes, cache changes, runtime changes, copy changes, navigation changes, or route behavior changes.
- Final diff is limited to this Markdown report.

## Executive decision

Liquidity Monitor and Rotation Radar are consumer-ready at the current source level: both pages translate
freshness, missing evidence, fallback/proxy states, and observation-only posture into user-facing product copy
instead of defaulting to backend diagnostics.

Do not open another backend DTO/provider/cache/runtime task from this audit. T-1046/T-1062 already classify
Rotation Radar as DTO-mature and Liquidity top-level `observationEvidenceSnapshot` as intentionally service-only.
The consumer gap visible here is test-side drift, not missing API authority metadata.

Recommend exactly one next write:

**T-1080-M1: Repair the Rotation Radar critical-route launch smoke to the current consumer surface.**

This should update the stale Rotation section in `apps/dsa-web/e2e/critical-route-launch-smoke.spec.ts` so it
asserts the current page title, guidance panel, summary band, mechanics disclosure, theme detail rail, no raw
diagnostic leakage, and no trading/action wording. The current smoke still asserts legacy copy/testids such as
`资金轮动雷达`, `下一观察 / 风险`, `只读证据`, and `rotation-theme-proxy-details-ai_applications`, none of which
exist in the current `MarketRotationRadarPage.tsx`. If needed, the write may also refresh the local
`marketRotationRadarPayload()` fixture in `apps/dsa-web/e2e/fixtures/appSmoke.ts` to include the current
`rotationFamilyRollup` / `themeFlowSignal` path, but it must remain fixture/test-only.

## Readiness matrix

| Surface | Consumer readiness | Existing test evidence | Remaining gap | Verdict |
| --- | --- | --- | --- | --- |
| Liquidity Monitor | Ready. The default consumer view suppresses technical diagnostics and maps score readiness, freshness, missing inputs, and observation-only signals into product copy. | Component tests cover first-screen safe copy, hidden admin diagnostics, capital-flow observation context, and raw field suppression. A dedicated Playwright degraded smoke covers `1440x1000` and `390x844`. | No immediate UI or API write. Keep future changes page-local and test-backed. | No next write from Liquidity. |
| Rotation Radar | Ready at component/source level. The page sanitizes internal terms, shows signal/freshness/readiness as consumer copy, folds mechanics and theme-flow detail, and fails closed on loading/timeouts. | Component tests cover default view, family rollup fallback, theme-flow disclosure, taxonomy/fallback states, error/loading paths, no raw diagnostic leakage, and no trading wording. General e2e smokes cover route launch, IA, collapsed disclosures, and no overflow. | The critical launch smoke is stale and does not match the current page surface. Some e2e fixtures also do not exercise newer family-flow fields. | Open one test-only repair. |

## Evidence

### Product and docs guardrails

- The consumer data-quality UX contract says consumer pages must not expose backend diagnostic vocabulary by
  default and must convert degraded data into product states
  (`docs/frontend/WOLFYSTOCK_CONSUMER_DATA_QUALITY_UX.md:13`,
  `docs/frontend/WOLFYSTOCK_CONSUMER_DATA_QUALITY_UX.md:27`).
- It explicitly forbids default-visible `sourceAuthorityAllowed`, `scoreContributionAllowed`, `observationOnly`,
  `reasonCode`, provider traces, provider class names, raw diagnostics, backend snake_case fields, and maintainer
  remediation instructions (`docs/frontend/WOLFYSTOCK_CONSUMER_DATA_QUALITY_UX.md:57`).
- Liquidity route guidance requires available/partial/paused/unavailable product states and forbids provider
  details, score-blocking field names, and fallback diagnostics in consumer copy
  (`docs/frontend/WOLFYSTOCK_CONSUMER_DATA_QUALITY_UX.md:141`).
- Rotation route guidance requires available/delayed/partial/insufficient signal states and forbids
  taxonomy/provider debug language in consumer copy
  (`docs/frontend/WOLFYSTOCK_CONSUMER_DATA_QUALITY_UX.md:148`).
- The data-quality policy requires material fallback/synthetic/demo/delayed limitations to be visible near
  decision-like outputs, while forbidding raw provider JSON, request URLs, credentials, account identifiers,
  raw prompts, cookies, tokens, and stack traces (`docs/audits/data-quality-user-disclosure-policy.md:45`,
  `docs/audits/data-quality-user-disclosure-policy.md:108`).
- Liquidity docs say source/risk detail belongs in bounded rail/disclosure, provider/cache/raw diagnostics must
  not become primary content, `capitalFlowSignal` stays observation-only, and missing/stale/fallback/synthetic
  inputs must not appear live or score strongly (`docs/liquidity/README.md:17`,
  `docs/liquidity/README.md:30`, `docs/liquidity/README.md:49`).
- Rotation docs say ranked themes/sectors should lead, source/freshness/fallback limits stay near conclusions,
  fallback/static/taxonomy-only themes are observation-only, and `consumerEvidenceSnapshot` excludes provider
  budgets, raw failure samples, source-authority internals, admin diagnostics, ranking trust, and raw provider
  payloads (`docs/rotation/README.md:17`, `docs/rotation/README.md:75`).

### Liquidity Monitor

- The page defines a consumer forbidden-copy pattern covering provider/proxy/fallback/source/authority/cache/raw
  diagnostics and snake_case-style terms (`apps/dsa-web/src/pages/LiquidityMonitorPage.tsx:1132`).
- Consumer summary helpers drop unsafe summaries and map score-ready, unavailable, observation-only, and partial
  indicators into product copy (`apps/dsa-web/src/pages/LiquidityMonitorPage.tsx:1157`,
  `apps/dsa-web/src/pages/LiquidityMonitorPage.tsx:1190`).
- The default non-admin branch renders `liquidity-decision-readiness`, `liquidity-summary-strip`,
  `liquidity-consumer-evidence`, `liquidity-context-rail`, and collapsed `数据说明与限制`; the admin technical
  details branch is skipped unless `showAdminDiagnostics` is true
  (`apps/dsa-web/src/pages/LiquidityMonitorPage.tsx:1879`,
  `apps/dsa-web/src/pages/LiquidityMonitorPage.tsx:2153`).
- The source/runtime disclosure with external calls, provider runtime, and cache mutation is inside the admin
  details path (`apps/dsa-web/src/pages/LiquidityMonitorPage.tsx:2270`).
- Frontend API types preserve indicator evidence, coverage diagnostics, `liquidityImpulseSynthesis`,
  `capitalFlowSignal`, and `sourceMetadata`, but the public normalized response still matches the current public
  DTO subset and does not expose top-level `observationEvidenceSnapshot`
  (`apps/dsa-web/src/api/liquidityMonitor.ts:163`, `apps/dsa-web/src/api/liquidityMonitor.ts:255`).
- Component tests verify the default consumer view hides admin diagnostics and does not show raw fields or
  provider/runtime/cache wording (`apps/dsa-web/src/pages/__tests__/LiquidityMonitorPage.test.tsx:716`).
- Component tests also verify compact consumer summary wording and no backend diagnostic leakage
  (`apps/dsa-web/src/pages/__tests__/LiquidityMonitorPage.test.tsx:774`).
- Capital-flow signal tests verify observation-only display and suppress raw authority/diagnostic fields
  (`apps/dsa-web/src/pages/__tests__/LiquidityMonitorPage.test.tsx:943`).
- The dedicated degraded Playwright smoke runs at `1440x1000` and `390x844`, mocks proxy-only/unavailable
  payloads, asserts consumer-safe degraded states, raw-term absence, no admin details, no horizontal overflow,
  and no console page errors (`apps/dsa-web/e2e/market-liquidity-monitor-degraded.spec.ts:5`,
  `apps/dsa-web/e2e/market-liquidity-monitor-degraded.spec.ts:170`).

Liquidity conclusion: no immediate write is needed. The next Liquidity change should happen only when a real
source/UI requirement appears, and it should reuse the existing `market-liquidity-monitor-degraded` smoke rather
than broadening provider/API scope.

### Rotation Radar

- The page sanitizes theme subtitles and fallback/freshness labels into consumer language
  (`apps/dsa-web/src/pages/MarketRotationRadarPage.tsx:248`,
  `apps/dsa-web/src/pages/MarketRotationRadarPage.tsx:263`).
- `sanitizeRotationText()` suppresses internal provider/source/proxy/fallback/static/taxonomy/debug terms and
  rewrites trading-action wording to research-framed copy
  (`apps/dsa-web/src/pages/MarketRotationRadarPage.tsx:477`,
  `apps/dsa-web/src/pages/MarketRotationRadarPage.tsx:492`).
- Rotation decision readiness maps payload state into consumer status, quality, blocker, and next-evidence copy
  (`apps/dsa-web/src/pages/MarketRotationRadarPage.tsx:799`).
- The default guidance panel renders the current state, selected theme, summary band, next step, family-flow
  observation rollup, and collapsed mechanics disclosure
  (`apps/dsa-web/src/pages/MarketRotationRadarPage.tsx:1074`,
  `apps/dsa-web/src/pages/MarketRotationRadarPage.tsx:1168`,
  `apps/dsa-web/src/pages/MarketRotationRadarPage.tsx:1219`).
- Theme-flow details and data notes are behind disclosures, not default first-viewport text
  (`apps/dsa-web/src/pages/MarketRotationRadarPage.tsx:1492`,
  `apps/dsa-web/src/pages/MarketRotationRadarPage.tsx:1535`).
- Loading fallback states explicitly avoid generating temporary rotation conclusions
  (`apps/dsa-web/src/pages/MarketRotationRadarPage.tsx:1562`).
- Frontend API normalization preserves `consumerEvidenceSnapshot`, provider state, theme quality, and
  `rotationFamilyRollup` while keeping raw provider payloads out of the adapter test fixture contract
  (`apps/dsa-web/src/api/marketRotation.ts:176`,
  `apps/dsa-web/src/api/marketRotation.ts:463`,
  `apps/dsa-web/src/api/__tests__/marketRotation.test.ts:391`).
- Component tests define raw i18n, diagnostic-leak, and forbidden trading/action patterns, then assert the default
  view has no raw diagnostics, no old diagnostic surfaces, and no trading wording
  (`apps/dsa-web/src/pages/__tests__/MarketRotationRadarPage.test.tsx:20`,
  `apps/dsa-web/src/pages/__tests__/MarketRotationRadarPage.test.tsx:759`).
- Component tests also cover family rollup fallback from `consumerEvidenceSnapshot` and verify it is
  consumer-safe (`apps/dsa-web/src/pages/__tests__/MarketRotationRadarPage.test.tsx:880`).
- Theme-flow disclosure tests verify observation detail stays collapsed by default and remains consumer-safe when
  expanded (`apps/dsa-web/src/pages/__tests__/MarketRotationRadarPage.test.tsx:919`).
- Market research e2e covers `/zh/market/rotation-radar` at `1440x1000` and `390x844`, asserting primary route
  roots, summary/universe visibility, collapsed disclosures, no overflow, and no trading CTA wording
  (`apps/dsa-web/e2e/market-research-surfaces.spec.ts:18`,
  `apps/dsa-web/e2e/market-research-surfaces.spec.ts:101`).

Rotation conclusion: the source/component readiness is good enough. The stale launch smoke is the only immediate
consumer-readiness write that should be opened.

## Why the next write is test-only

The current `critical-route-launch-smoke.spec.ts` Rotation helper still asserts legacy route shape:

- old visible copy: `下一观察 / 风险`, `只读证据`, `非交易指令`
  (`apps/dsa-web/e2e/critical-route-launch-smoke.spec.ts:85`);
- old proxy disclosure testid: `rotation-theme-proxy-details-ai_applications`
  (`apps/dsa-web/e2e/critical-route-launch-smoke.spec.ts:90`);
- old page heading expectation: `资金轮动雷达`
  (`apps/dsa-web/e2e/critical-route-launch-smoke.spec.ts:187`).

Current `MarketRotationRadarPage.tsx` instead renders `主题轮动雷达`, `rotation-radar-guidance`,
`rotation-radar-summary-band`, `rotation-radar-visual-matrix` / `rotation-radar-visual-unavailable`,
`rotation-radar-universe-list`, `rotation-theme-detail-panel`, `rotation-theme-data-notes`, and
`rotation-radar-mechanics-details` (`apps/dsa-web/src/pages/MarketRotationRadarPage.tsx:1762`,
`apps/dsa-web/src/pages/MarketRotationRadarPage.tsx:1791`).

The app-smoke fixture also exercises an older Rotation payload shape: it returns strongest/accelerating/fading
themes plus theme detail, but no `summary.rotationFamilyRollup`, no `consumerEvidenceSnapshot`, and no
`themeFlowSignal` (`apps/dsa-web/e2e/fixtures/appSmoke.ts:310`,
`apps/dsa-web/e2e/fixtures/appSmoke.ts:327`, `apps/dsa-web/e2e/fixtures/appSmoke.ts:343`).

This does not justify a source rewrite. It only means the launch smoke should be brought back in line with the
current consumer surface, and the fixture may be refreshed if the repaired smoke wants to prove the family-flow
path in a browser.

## Recommended next task

Open one future implementation task:

**T-1080-M1: Rotation Radar critical-route smoke current-surface repair**

Goal:

- Update `assertRotationRadarReadOnlyShell()` and the Rotation route assertions in
  `critical-route-launch-smoke.spec.ts` to the current consumer page contract.
- Assert current visible anchors: `主题轮动雷达`, `rotation-radar-guidance`, `rotation-radar-summary-band`,
  `rotation-radar-universe-list`, `rotation-theme-detail-panel`, `rotation-radar-mechanics-details`, and either
  `rotation-radar-visual-matrix` or `rotation-radar-visual-unavailable` depending on fixture state.
- Assert old diagnostic surfaces remain absent.
- Assert no raw diagnostic leakage and no trading/action wording in both desktop and mobile viewports.
- Keep the write test-only.

Allowed future write files:

- `apps/dsa-web/e2e/critical-route-launch-smoke.spec.ts`

Optional only if the repaired smoke needs a richer current payload:

- `apps/dsa-web/e2e/fixtures/appSmoke.ts`

Forbidden files for T-1080-M1:

- `src/**`
- `api/**`
- `data_provider/**`
- `apps/dsa-web/src/**`
- `apps/dsa-web/package.json`
- lockfiles, root config, CI, Docker, env templates, docs except an optional task note if explicitly requested

Forbidden semantic changes:

- no provider additions or provider order changes;
- no live-call, retry, timeout, fallback, entitlement, cache, TTL, SWR, or MarketCache changes;
- no API/DTO/schema response shape changes;
- no Liquidity score contribution or Rotation rank/headline/score/source-authority changes;
- no UI source/component rewrite;
- no trading/advice copy.

Focused validation for T-1080-M1:

```bash
DSA_WEB_PLAYWRIGHT_PORT=4280 npm --prefix apps/dsa-web run test:e2e -- e2e/critical-route-launch-smoke.spec.ts --project=chromium -g "market rotation radar stays clean"
DSA_WEB_PLAYWRIGHT_PORT=4281 npm --prefix apps/dsa-web run test:e2e -- e2e/market-research-surfaces.spec.ts --project=chromium
npm --prefix apps/dsa-web run test -- src/pages/__tests__/MarketRotationRadarPage.test.tsx --no-file-parallelism
git diff --check -- apps/dsa-web/e2e/critical-route-launch-smoke.spec.ts apps/dsa-web/e2e/fixtures/appSmoke.ts
```

Escalate to broader e2e only if the smoke repair reveals page behavior drift, not merely fixture/test drift.

## Explicit deferrals

Defer all of the following from the next write:

- Liquidity public `observationEvidenceSnapshot` publication.
- Rotation DTO/schema tightening.
- `themeFlowSignal` or `rotationFamilyRollup` service semantics changes.
- Liquidity/Rotation provider activation or source-authority adoption.
- Any frontend layout rewrite or global primitive/token sweep.
- Any copy change that could read as trading recommendation, execution readiness, or valuation advice.

## Final audit decision

Proceed with exactly one test-only repair:

**T-1080-M1: Rotation Radar critical-route smoke current-surface repair.**

Do not open Liquidity UI work, backend DTO work, provider/cache/runtime work, or broad consumer-copy redesign from
this audit.

## Final diff confirmation for this audit

- This T-1080 task is report-only.
- No source code changed.
- No tests changed.
- No config/package/lockfile changes.
- No provider/cache/runtime/network/API/frontend behavior changes.
- No browser verification was run, because this is a docs-only audit and the recommended write is future
  test-only repair.
