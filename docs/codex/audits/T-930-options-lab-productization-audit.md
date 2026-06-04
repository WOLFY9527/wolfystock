# T-930 Options Lab Productization Audit

Task ID: T-930
Mode: READ-ONLY-AUDIT with task-authorized docs-only report and local commit
Scope: Options Lab productization audit. No runtime code was changed.

## Executive Verdict

Options Lab is safe enough as a read-only analytical lab, but it is not yet
productized as a coherent consumer research workflow.

The current implementation already has strong no-broker, no-order,
no-portfolio-mutation, no-trading-recommendation, fixture/demo fail-closed, and
sanitized-error boundaries. The product gap is different: the user still sees a
lab made from controls, chain tables, strategy comparisons, decision metrics,
and warnings, instead of one readiness-first workflow that answers:

```text
Can this options scenario be researched safely?
What evidence is missing?
Which risk structure is worth observing?
What must stay out of scope?
```

The next work should not widen provider behavior, broker/order surfaces,
portfolio mutation, strategy math, payoff math, Greeks/IV assumptions, cache
semantics, or LLM routing. It should first add a consumer-safe product contract
and workflow information architecture that projects existing evidence into a
clear research path.

## Guardrails Applied

This audit followed:

- `AGENTS.md`
- `docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md`
- `docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md`
- `docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md`
- `docs/codex/audits/T-892-research-os-product-gap-audit.md`

Task-specific constraints:

- Allowed final diff: this audit document only.
- Forbidden: runtime code, frontend TSX/CSS, backend endpoint/service/provider,
  cache/storage/auth/accounting, strategy math/payoff/Greeks/IV, broker/order,
  trading, portfolio mutation, LLM prompt/model/routing, provider probing/live
  calls, config/lockfile/CI, and raw logs/secrets in docs.
- Subagents were used only for read-only scouting and risk review; the main
  agent owns this synthesis.

## Current Backend Inventory

Options Lab is not an empty shell. The API router mounts the Options endpoint
family under `/api/v1/options` (`api/v1/router.py:211`).

Current endpoint family in `api/v1/endpoints/options.py`:

- `GET /underlyings/{symbol}/summary`
  (`api/v1/endpoints/options.py:454`)
- `GET /underlyings/{symbol}/expirations`
  (`api/v1/endpoints/options.py:478`)
- `GET /underlyings/{symbol}/chain`
  (`api/v1/endpoints/options.py:502`)
- `POST /analyze`
  (`api/v1/endpoints/options.py:538`)
- `POST /decision/evaluate`
  (`api/v1/endpoints/options.py:554`)
- `POST /scenario`
  (`api/v1/endpoints/options.py:570`)
- `POST /strategies/compare`
  (`api/v1/endpoints/options.py:586`)

The service flow is:

```text
endpoint mapper
-> OptionsLabService
-> OptionsMarketDataProvider
-> public Options DTO
-> schema-level optionsReadiness/optionsResearchReadiness projection
```

Relevant implementation seams:

- `OptionsLabService` is explicitly fixture-backed and avoids live providers,
  LLMs, broker execution, and portfolio mutation
  (`src/services/options_lab_service.py:1`).
- Summary, expirations, chain, analyze, scenario, strategy compare, and
  decision evaluation are service-local flows
  (`src/services/options_lab_service.py:161`,
  `src/services/options_lab_service.py:187`,
  `src/services/options_lab_service.py:216`,
  `src/services/options_lab_service.py:271`,
  `src/services/options_lab_service.py:336`,
  `src/services/options_lab_service.py:388`,
  `src/services/options_lab_service.py:438`).
- Decision evaluation combines data quality, liquidity, IV/Greeks, breakeven,
  risk/reward, expected move, strategy optimizer, and gate diagnostics
  (`src/services/options_lab_service.py:453`).
- Strategy comparison supports long call, long put, bull call spread, and bear
  put spread, with debit-spread payoff math kept inside the service
  (`src/services/options_lab_service.py:1889`).
- Scenario currently computes deterministic expiration payoff rows for single
  long option structures only; pre-expiration theoretical pricing is explicitly
  unavailable (`src/services/options_lab_service.py:336`,
  `src/services/options_lab_service.py:374`).

## Current Schema And Readiness Inventory

Public schemas already encode most safety and readiness vocabulary:

- `OptionsMetadata` exposes read-only, fixture/synthetic, no external calls, no
  LLM calls, no order placement, no broker connection, no portfolio mutation,
  no trading recommendation, provider name/capabilities, and live-provider
  status (`api/v1/schemas/options.py:30`).
- `OptionContract` carries bid/ask/mid/last, volume, open interest, IV, Greeks,
  DTE, moneyness, spread percent, liquidity bucket, freshness, provider quality,
  data quality, and warnings (`api/v1/schemas/options.py:66`).
- `OptionsResearchReadiness` exposes `optionsResearchReady`,
  `readinessState`, `dataQualityTier`, `decisionGrade`, `providerAuthority`,
  `liquidityGate`, `ivGreeksGate`, `spreadGate`, `scenarioCoverage`,
  `noTradingBoundary`, `blockingReasons`, and `nextEvidenceNeeded`
  (`api/v1/schemas/options.py:238`).
- Response validators populate both `optionsReadiness` and
  `optionsResearchReadiness` aliases on summary, expirations, chain, analyze,
  scenario, strategy compare, and decision responses
  (`api/v1/schemas/options.py:113`, `api/v1/schemas/options.py:145`,
  `api/v1/schemas/options.py:181`, `api/v1/schemas/options.py:664`,
  `api/v1/schemas/options.py:725`, `api/v1/schemas/options.py:796`,
  `api/v1/schemas/options.py:981`).

Gate/readiness logic already fails closed:

- Missing contracts, missing bid/ask, wide spreads, missing IV, missing Greeks,
  missing volume, and missing open interest become blocking or review signals
  (`api/v1/schemas/options.py:356`, `api/v1/schemas/options.py:374`,
  `api/v1/schemas/options.py:382`, `api/v1/schemas/options.py:394`).
- Fixture, synthetic, dry-run, adapter-contract, disabled-live, missing
  tradeable-data, and missing authority tiers become provider blocking reasons
  (`api/v1/schemas/options.py:295`).
- Decision-grade requires live usable data, score-grade provider authority,
  clear liquidity gate, clear IV/Greeks gate, and clear spread gate
  (`api/v1/schemas/options.py:532`).

Provider and authority helpers are protected seams:

- `src/services/options_data_quality_gates.py` owns offline-only gate
  diagnostics and labels.
- `src/services/options_market_data_provider.py` owns fixture providers,
  disabled live stubs, dry-run mapping, provider preflight, and sanitized
  credential-readiness counts.
- `src/services/options_authority_policy_matrix.py`,
  `src/services/options_iv_rank_authority.py`,
  `src/services/options_expiration_calendar_authority.py`, and
  `src/services/options_event_calendar_authority.py` own authority policy
  projections and should not be casually changed by UI productization tasks.

## Current Frontend Inventory

Options Lab is a registered product route:

- `/options-lab` and `/:locale/options-lab` render through registered product
  routing (`apps/dsa-web/src/App.tsx:385`, `apps/dsa-web/src/App.tsx:412`).
- Sidebar and shell labels still call it "期权实验室", reinforcing the lab
  posture (`apps/dsa-web/src/components/layout/SidebarNav.tsx:89`,
  `apps/dsa-web/src/components/layout/Shell.tsx:62`,
  `apps/dsa-web/src/i18n/core.ts:14`).

The page is largely implemented in one large route file:

- `ProductHero` shows availability, shared research readiness, Options gate
  summary, symbol, price, and no-execution copy
  (`apps/dsa-web/src/pages/OptionsLabPage.tsx:781`).
- `AssumptionPanel` gathers symbol, target price, target date, expiration, risk
  budget, direction, and risk profile
  (`apps/dsa-web/src/pages/OptionsLabPage.tsx:592`).
- `StrategyComparisonPanel` displays candidate strategies
  (`apps/dsa-web/src/pages/OptionsLabPage.tsx:998`).
- `DecisionPanel` displays the scenario judgment, readiness strip, quality
  score, max loss, expected move, IV/Greeks readiness, breakeven, IV rank, and
  observed structure (`apps/dsa-web/src/pages/OptionsLabPage.tsx:1080`).
- `ChainTable` displays calls and puts in dense tables
  (`apps/dsa-web/src/pages/OptionsLabPage.tsx:877`).
- `RiskBoundaryPanel` and `ContextRailPanel` summarize visible risk warnings
  and next steps (`apps/dsa-web/src/pages/OptionsLabPage.tsx:1202`,
  `apps/dsa-web/src/pages/OptionsLabPage.tsx:1328`).
- `MethodologyDisclosure` keeps method/data notes collapsed
  (`apps/dsa-web/src/pages/OptionsLabPage.tsx:1354`).

Current data flow:

- On load, the page fetches summary and expirations, then fetches the selected
  chain (`apps/dsa-web/src/pages/OptionsLabPage.tsx:1458`).
- When prerequisites are ready, it automatically requests strategy comparison
  (`apps/dsa-web/src/pages/OptionsLabPage.tsx:1505`).
- When prerequisites are ready, it automatically evaluates decision readiness
  with a hard-coded `bull_call_spread` strategy
  (`apps/dsa-web/src/pages/OptionsLabPage.tsx:1588`,
  `apps/dsa-web/src/pages/OptionsLabPage.tsx:1605`).
- The page extracts additive Options readiness from summary, expirations, chain,
  comparison, and decision payloads, then maps it into the shared consumer
  research readiness strip (`apps/dsa-web/src/pages/OptionsLabPage.tsx:1715`).

The Options gate summary component is already consumer-safe:

- Missing readiness fails closed to blocked/insufficient with no-trading
  boundary intact
  (`apps/dsa-web/src/components/options/OptionsReadinessGateSummary.tsx:13`).
- Raw reason codes are mapped to consumer labels such as authority, IV/Greeks,
  liquidity, chain, demo, and next evidence
  (`apps/dsa-web/src/components/options/OptionsReadinessGateSummary.tsx:104`,
  `apps/dsa-web/src/components/options/OptionsReadinessGateSummary.tsx:161`).

## Current Tests And Browser Smoke

Backend tests already cover key safety and readiness seams:

- Service fixture/non-live provenance and no external path behavior
  (`tests/test_options_lab_service.py:146`,
  `tests/test_options_lab_service.py:159`,
  `tests/test_options_lab_service.py:258`,
  `tests/test_options_lab_service.py:266`).
- Scenario payoff determinism
  (`tests/test_options_lab_service.py:429`).
- Strategy compare structures, max-premium filtering, unsupported strategies,
  no external/mutating paths, and no raw advice/order fields
  (`tests/test_options_lab_service.py:479`,
  `tests/test_options_lab_service.py:555`,
  `tests/test_options_lab_service.py:576`,
  `tests/test_options_lab_service.py:592`,
  `tests/test_options_lab_service.py:615`).
- Decision fail-closed data quality, IV rank, expected move, optimizer, missing
  Greeks, wide spread, delayed/non-live caps, stale data degradation, cached
  fallback/synthetic caps, no raw provider secret/live paths, and additive gate
  diagnostics (`tests/test_options_lab_service.py:682`,
  `tests/test_options_lab_service.py:711`,
  `tests/test_options_lab_service.py:752`,
  `tests/test_options_lab_service.py:810`,
  `tests/test_options_lab_service.py:857`,
  `tests/test_options_lab_service.py:887`,
  `tests/test_options_lab_service.py:915`,
  `tests/test_options_lab_service.py:939`,
  `tests/test_options_lab_service.py:983`,
  `tests/test_options_lab_service.py:1112`,
  `tests/test_options_lab_service.py:1138`).
- API endpoint no-live/no-mutation/no-leak behavior, scenario, strategy compare,
  decision, live-provider fail-closed, readiness detection, delayed/live states,
  and source import sentinels (`tests/api/test_options_lab.py:444`,
  `tests/api/test_options_lab.py:573`,
  `tests/api/test_options_lab.py:597`,
  `tests/api/test_options_lab.py:725`,
  `tests/api/test_options_lab.py:786`,
  `tests/api/test_options_lab.py:1216`,
  `tests/api/test_options_lab.py:1248`,
  `tests/api/test_options_lab.py:1314`,
  `tests/api/test_options_lab.py:1346`,
  `tests/api/test_options_lab.py:1383`,
  `tests/api/test_options_lab.py:1458`,
  `tests/api/test_options_lab.py:1804`,
  `tests/api/test_options_lab.py:1935`,
  `tests/api/test_options_lab.py:2150`).

Frontend tests already cover consumer-safe presentation:

- Hero gate summary appears near the top, maps raw gate values to consumer copy,
  and fails closed when readiness is missing
  (`apps/dsa-web/src/pages/__tests__/OptionsLabPage.test.tsx:663`,
  `apps/dsa-web/src/pages/__tests__/OptionsLabPage.test.tsx:686`).
- Delayed usable readiness remains observation-bounded
  (`apps/dsa-web/src/pages/__tests__/OptionsLabPage.test.tsx:702`).
- Gate issue objects are sanitized and do not leak raw codes or trading wording
  (`apps/dsa-web/src/pages/__tests__/OptionsLabPage.test.tsx:733`).
- Maintainer setup actions and provider/admin details stay out of the default
  consumer view
  (`apps/dsa-web/src/pages/__tests__/OptionsLabPage.test.tsx:876`).
- Decision-grade payloads still render as review/observation bounded
  (`apps/dsa-web/src/pages/__tests__/OptionsLabPage.test.tsx:890`).
- Decision summary appears ahead of deep chain and limitation detail
  (`apps/dsa-web/src/pages/__tests__/OptionsLabPage.test.tsx:1053`).
- Assumption changes recompute comparison and decision requests
  (`apps/dsa-web/src/pages/__tests__/OptionsLabPage.test.tsx:1194`).
- Missing prerequisites, compare failures, auth-gated base data, malformed
  payloads, loading/empty/error states, and route visibility are guarded
  (`apps/dsa-web/src/pages/__tests__/OptionsLabPage.test.tsx:1327`,
  `apps/dsa-web/src/pages/__tests__/OptionsLabPage.test.tsx:1365`,
  `apps/dsa-web/src/pages/__tests__/OptionsLabPage.test.tsx:1470`,
  `apps/dsa-web/src/pages/__tests__/OptionsLabPage.test.tsx:1638`,
  `apps/dsa-web/src/pages/__tests__/OptionsLabPage.test.tsx:1664`,
  `apps/dsa-web/src/pages/__tests__/OptionsLabPage.test.tsx:1694`).
- Static copy sentinels keep visible framing analytical and no-decision grade
  (`apps/dsa-web/src/pages/tests/OptionsLabPage.test.tsx:8`).

Browser acceptance currently covers readiness visibility and safety:

- `readiness-browser-acceptance.smoke.spec.ts` checks desktop/mobile viewports,
  root non-empty, no horizontal overflow, consumer-safe readiness strip, Options
  gate summary visibility, no internal leakage, and no trading wording
  (`apps/dsa-web/e2e/readiness-browser-acceptance.smoke.spec.ts:852`).

Known browser-smoke maintenance gap:

- Some older route launch smokes appear to reference stale Options Lab test IDs
  such as `options-lab-assumptions-row`, `options-lab-chain-details`, or older
  disclosure copy. UI write tasks should repair those stale tests before using
  them as productization proof.

## Why It Still Feels Non-Productized

### 1. The Primary Decision Path Is Still Implicit

The current route asks the user for a symbol, target price, target date,
expiration, budget, direction, and risk profile, then automatically runs
comparison and decision evaluation. It does not explicitly frame a single
workflow such as:

```text
Input scenario
-> chain quality and authority check
-> scenario coverage
-> candidate risk structures
-> decision boundary
-> next evidence needed
```

Instead, the page renders a hero, summary strip, command panel, strategy panel,
decision panel, chain tables, risk rail, context rail, and methodology
disclosure as adjacent workbench surfaces.

### 2. The UI Still Centers Lab Controls And Dense Tables

The route still uses labels like "期权实验室", "情景控制台", "刷新情景",
"链表工作区", and "数据注记". These are safe labels, but they preserve the
mental model of operating a lab rather than following a product workflow.

Dense call/put chain tables still occupy meaningful screen area. They are
valuable, but they are not the first consumer question. Productized Options Lab
should first answer evidence readiness and scenario risk structure, then let the
user inspect chain details.

### 3. Scenario UX Is Weak Relative To The Backend

The backend has a `/scenario` endpoint and deterministic expiration payoff
model, but the frontend API client and page do not expose a typed scenario call
or a scenario evidence projection. The current UI infers scenario posture mostly
from strategy compare and decision payloads.

This makes "what happens if the underlying moves?" feel indirect. The page
should show scenario coverage as a first-class product concept: target move,
breakeven pressure, max loss, expected move source, IV/Greeks readiness, and
what is missing.

### 4. Evidence Hierarchy Is Still Noisy

There are many useful evidence elements: provider authority, data tier,
liquidity, spread, IV/Greeks, expected move, IV rank, risk/reward, optimizer,
strategy alternatives, fail-closed reasons, limitations, warnings, chain
fields, and method notes.

The current page translates many raw details into safe labels, but it does not
yet enforce one hierarchy:

1. Is the Options scenario research-ready?
2. What evidence blocks it?
3. Which risk structure is only observation-worthy?
4. What details are inspectable but not headline-worthy?

### 5. Frontend Type Contract Lags The Backend

The backend exposes structured gate issue objects and gate summaries, while the
frontend API type keeps parts of these fields as generic records or string
arrays. This is tolerable for a lab view, but product UI should not depend on
loose records for gate evidence.

### 6. Compare Readiness Is Not Leg-Derived

`OptionsStrategyCompareResponse` currently auto-builds readiness with an empty
contracts list and `scenarioCoverage=strategy_compare_ready`. That proves the
compare surface has a readiness alias, but not that readiness is derived from
the actual strategy legs' liquidity, IV/Greeks, and spread evidence.

### 7. Strategy Source Of Truth Is Unclear

The page hard-codes decision evaluation to `bull_call_spread` while comparison
can rank multiple strategies. A product workflow needs a clear source of truth:
the user's selected structure, the top observation candidate, or a fail-closed
"no selected structure" state.

## Consumer-Safe Product Contract

The next product-grade contract should be projection-only and additive. It
should reuse current service outputs and shared readiness helpers instead of
changing provider runtime, gate math, payoff math, strategy ranking, or old
response fields.

### Inputs

Minimum consumer inputs:

- `symbol`
- `direction`: bullish, bearish, neutral, volatility
- `targetPrice`
- `targetDate`
- `riskBudget`
- `expiration`
- optional selected strategy/structure

The product contract should distinguish user assumptions from evidence. User
inputs can drive scenario calculations, but they must not become provider
authority or decision-grade proof.

### Evidence Required

Product-grade Options research requires these evidence buckets:

- Underlying snapshot: price, source, freshness, as-of.
- Expiration coverage: selected expiration exists, DTE known, chain available.
- Chain quality: normalized calls/puts, bid/ask/mid, multiplier, strikes,
  volume, open interest, IV, Greeks, contract source, freshness.
- Liquidity gate: bid/ask coverage, spread threshold, OI, volume, mid validity,
  leg-level diagnostics.
- IV/Greeks gate: IV availability, Greeks coverage, IV rank/percentile source
  and confidence, expected move source.
- Spread gate: missing/wide/manual-review spread status.
- Scenario coverage: missing chain, single contract, strategy compare, and
  future spread scenario coverage.
- Strategy comparison: max loss, max gain, breakeven, required move, payoff at
  target, risk/reward, leg warnings.
- Decision boundary: research-ready state, decision-grade false/true, no-advice,
  no-execution, no broker, no order, no portfolio mutation.

### Output Contract

Recommended additive projection:

```text
OptionsProductReadinessV1
  contractVersion
  optionsResearchReady
  readinessState
  dataQualityTier
  providerAuthority
  chainQuality
  liquidityGate
  ivGreeksGate
  spreadGate
  scenarioCoverage
  strategyComparisonState
  decisionGrade
  consumerActionBoundary
  noTradingBoundary
  blockingReasons
  missingEvidence
  nextEvidenceNeeded
```

Recommended consumer scenario projection:

```text
OptionsConsumerScenarioFrame
  inputScenario
  selectedOrObservedStructure
  chainQualitySummary
  liquidityEvidence
  ivGreeksEvidence
  expectedMoveEvidence
  breakevenPressure
  maxLossBoundary
  comparisonSummary
  observationBoundary
  nextEvidenceNeeded
```

This projection can become product-grade without broker/order integration. It
should remain a research workflow and explicitly avoid execution CTAs.

## What Can Become Product-Grade Without Broker/Order Integration

These areas are safe candidates for product-grade work:

- A readiness-first workflow IA that makes scenario readiness the first
  question.
- A typed frontend contract that matches backend DTOs and stops treating gate
  evidence as loose records.
- A typed `/scenario` frontend client and scenario evidence projection.
- A clear source-of-truth rule for selected/observed strategy.
- A consumer-safe summary of chain quality, liquidity, IV/Greeks, spread, and
  scenario coverage.
- A compact product hero and decision summary that show observe-only,
  insufficient, blocked, or ready states before any technical detail.
- Browser/API smokes proving no raw provider/debug/secret leakage and no
  broker/order/portfolio mutation or trading recommendation wording.

These areas should remain out of scope:

- Broker connection, order placement, or account actions.
- Portfolio mutation, portfolio accounting, cost basis, holdings, cash, P&L,
  replay, sync, or imports.
- Provider live-call enablement, provider order changes, fallback changes,
  MarketCache behavior, or credential handling.
- Strategy math, payoff math, Greeks/IV assumptions, thresholds, optimizer
  ranking, or no-trade policy changes.
- LLM prompts, model routing, recommendation semantics, or prompt fallback.

## Protected Domains

Do not touch these domains in productization UI/docs/test tasks unless a future
task explicitly scopes them:

- Options ranking, gates, scoring, recommendation policy, optimizer/no-trade
  policy, payoff math, strategy math, Greeks, IV, and expected-move assumptions.
- API response shape or stored contract versions, except additive projection
  fields in explicitly allowed files.
- Provider runtime order, live-call paths, fallback semantics, data freshness
  semantics, provider credentials, and raw payload handling.
- Broker, order, execution, account, and portfolio mutation surfaces.
- Portfolio accounting, cash, holdings, P&L, sync, import, replay, FX, and cost
  basis.
- Auth/RBAC/security, config, CI, lockfiles, dependencies, cache/storage, and
  LLM prompts/routing.

## Tests Required Before Any Write

### Before Backend/API Contract Writes

Run or extend focused backend tests before implementation:

- `tests/api/test_options_lab.py`
  - endpoint alias compatibility;
  - no raw payload/secret/live-provider leakage;
  - no broker/order/portfolio mutation imports;
  - `optionsReadiness` and `optionsResearchReadiness` compatibility;
  - fixture, delayed, live-shaped, missing chain, missing bid/ask, wide spread,
    missing IV/Greeks states.
- `tests/test_options_lab_service.py`
  - service flow, scenario, compare, decision, optimizer, no external calls,
    no mutation paths, no raw leakage.
- `tests/test_options_data_quality_gates.py`
  - gate diagnostics, provider authority, event calendar, IV rank, expected
    move, fail-closed reason codes.
- `tests/test_options_market_data_provider.py`
  - fixture providers, live stubs, dry-run mapping, sanitized credential
    readiness.
- `tests/test_options_authority_policy_matrix.py`
  - only if policy matrix behavior is explicitly in scope.

### Before Frontend/UI Writes

Run or extend focused frontend tests before implementation:

- `apps/dsa-web/src/api/__tests__/optionsLab.test.ts`
  - typed DTO compatibility;
  - `/scenario` client once added;
  - fixture/fallback and sanitized error handling.
- `apps/dsa-web/src/pages/__tests__/OptionsLabPage.test.tsx`
  - workflow order;
  - strategy source of truth;
  - readiness-first summary;
  - scenario evidence projection;
  - empty/error/malformed payload states;
  - no raw/internal leakage.
- `apps/dsa-web/src/pages/tests/OptionsLabPage.test.tsx`
  - copy sentinels for no-decision/no-execution boundaries.
- Browser smokes:
  - `apps/dsa-web/e2e/readiness-browser-acceptance.smoke.spec.ts`
  - `apps/dsa-web/e2e/public-safety-ai-scanner-options.smoke.spec.ts`
  - stale Options route smokes should be repaired before they are used as
    productization evidence.

## Phased Write Tasks

### T-935 Options Lab Workflow IA Contract

Purpose: define and expose the consumer-safe product workflow contract without
changing runtime behavior.

Suggested allowed final diff:

- `docs/codex/audits/T-935-options-lab-workflow-ia-contract.md`
- Optional focused tests only if the task explicitly moves from docs to
  execution.

Implementation intent:

- Define `OptionsProductReadinessV1` and `OptionsConsumerScenarioFrame` as
  projection contracts.
- Specify workflow ordering: input scenario, chain quality, scenario coverage,
  strategy comparison, decision boundary, next evidence.
- Define strategy source of truth.
- Define consumer copy vocabulary: observe-only, evidence insufficient, blocked,
  research-ready, no-advice, no-execution.

Forbidden:

- No backend service/endpoint/provider/cache edits.
- No frontend TSX/CSS edits unless explicitly rescope.
- No strategy/gate/math/provider/portfolio/broker/order changes.

Tests required before write:

- Identify exact backend and frontend tests that will guard the contract before
  any runtime integration task begins.

### T-936 Options Scenario Evidence Projection

Purpose: add a projection-only scenario evidence layer that consumes existing
summary, chain, scenario, compare, and decision evidence.

Suggested allowed final diff:

- Focused projection helper/types/tests, to be selected by the future prompt.
- No provider/runtime/cache/math edits.

Implementation intent:

- Add typed frontend API support for `/scenario` if scoped frontend-only, or add
  backend projection if scoped backend-only.
- Project target move, breakeven pressure, expected move source, max loss,
  chain coverage, liquidity, IV/Greeks, and missing evidence.
- Fail closed when scenario payload, selected contract, IV/Greeks, bid/ask, OI,
  volume, or provider authority is missing.

Forbidden:

- No payoff math changes.
- No Greeks/IV assumption changes.
- No live provider calls.
- No broker/order/portfolio integration.

Tests required before write:

- API/service fixture tests for missing chain, missing bid/ask, missing Greeks,
  unavailable expected move, and delayed/fresh states.
- Frontend API/page tests for scenario absent, scenario partial, and scenario
  present.

### T-937 Options Consumer UI Refinement

Purpose: reshape the page into a coherent consumer research workflow while
preserving the no-trading boundary.

Suggested allowed final diff:

- `apps/dsa-web/src/pages/OptionsLabPage.tsx`
- `apps/dsa-web/src/components/options/*` if needed
- focused frontend tests and browser smokes

Implementation intent:

- Put readiness and scenario summary before strategy and chain detail.
- Treat chain tables as inspectable evidence, not the primary product.
- Keep controls compact and make "next evidence needed" explicit.
- Use one bounded disclosure/rail for limitations and method detail.
- Preserve existing route, auth, API calls, and test IDs where possible.

Forbidden:

- No backend changes.
- No provider/runtime/cache/auth/config changes.
- No strategy math/payoff/Greeks/IV changes.
- No broker/order/portfolio mutation.
- No trading recommendation or execution CTA wording.

Tests required before write:

- Page tests proving section order, strategy source of truth, fail-closed
  readiness, no raw leakage, no forbidden wording, malformed payload resilience.
- Browser smoke on desktop and mobile for no horizontal overflow, visible
  readiness/scenario summary, no console errors, and no raw/internal leakage.

### T-938 Options Browser/API Productization Smoke

Purpose: add acceptance coverage proving the productized workflow is safe and
non-execution-grade.

Suggested allowed final diff:

- `apps/dsa-web/e2e/*options*.spec.ts`
- focused API/browser test fixtures only

Implementation intent:

- Cover `/zh/options-lab` with authenticated product harness.
- Assert readiness-first workflow sections appear in order.
- Assert scenario evidence, chain quality, strategy comparison, and decision
  boundary are visible without raw codes.
- Assert missing readiness, fixture/demo, delayed usable, live-shaped, and
  malformed payload states fail closed.
- Assert no raw provider/debug/schema/cache/router/env/sourceAuthority/provider
  route leakage.
- Assert no broker/order/portfolio mutation and no trading recommendation
  wording.

Forbidden:

- No product code changes unless the future task explicitly rescope from
  tests-only.
- No provider/live probing.
- No backend service/provider/cache edits.

Tests required before write:

- Repair stale Options route smokes before adding new assertions.
- Use route mocking, not live provider calls.

## Recommended Sequence

1. T-935: lock the workflow IA and product contract.
2. T-936: add scenario evidence projection.
3. T-937: refine consumer UI around the projection.
4. T-938: add browser/API productization smoke.

This order avoids premature UI reshaping before the contract is stable, and it
avoids protected backend math/provider changes while still making the surface
feel productized.

## Audit Closeout

Current status: PLANNED.

This audit intentionally did not implement runtime changes. The implementation
surface is ready for narrowly scoped follow-up tasks, but Options Lab should
stay observation-only until evidence hierarchy, scenario projection, and browser
acceptance are in place.
