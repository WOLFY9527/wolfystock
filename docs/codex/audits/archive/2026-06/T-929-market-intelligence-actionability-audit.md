# T-929 Market Intelligence Actionability Audit

Task ID: T-929
Mode: READ-ONLY-AUDIT
Scope: docs-only implementation-ready audit. No runtime code was changed by
this task.

## Executive Verdict

Market Intelligence is no longer missing all readiness primitives. The backend
already attaches a `researchReadiness` projection to `/api/v1/market/temperature`
through the shared `ResearchReadinessV1` helper, and the frontend already shows a
top-level research-readiness strip on Market Overview. The product gap is that
these signals remain too narrow and too fragmented to answer the investor's
practical question: "Can I use this market state as a trustworthy research
direction, what is missing, and what should I check next?"

The safe next direction is not a new score engine, provider fanout, or trading
recommendation layer. Market Intelligence should reuse `ResearchReadinessV1` as
the only consumer-facing verdict contract, then add an additive
`marketActionabilityFrame` projection that consumes existing Market Overview,
Liquidity, Rotation, Scanner context, and evidence-readiness outputs without
changing provider order, scoring, ranking, cache behavior, API semantics, or
trading boundaries.

## Current Inventory

### Routes and APIs

- Market Intelligence routes are split between legacy Market Overview panels and
  newer Market endpoints. The API router mounts `/api/v1/market-overview/*`,
  `/api/v1/market/*`, and Liquidity Monitor under `/api/v1/market/*`
  (`api/v1/router.py:186-201`).
- The legacy Market Overview endpoint group exposes `indices`, `volatility`,
  `sentiment`, `funds-flow`, and `macro`, each directly backed by
  `MarketOverviewService` (`api/v1/endpoints/market_overview.py:29-50`).
- The broader Market endpoint group exposes `crypto`, `sentiment`, `cn-indices`,
  `cn-breadth`, `cn-flows`, `sector-rotation`, `rotation-radar`,
  `us-breadth`, `rates`, `fx-commodities`, `temperature`,
  `market-briefing`, `futures`, `cn-short-sentiment`, provider-health,
  provider-fit, and local `data-readiness` diagnostics
  (`api/v1/endpoints/market.py:62-203`).
- Liquidity Monitor is a separate market route and response model under
  `/api/v1/market/liquidity-monitor` (`api/v1/endpoints/liquidity_monitor.py:15`).

### Backend Data and Evidence Paths

- `MarketOverviewService.get_market_temperature()` is the current strongest
  backend assembly point. It builds temperature inputs, trust gates, scores,
  `marketRegimeSynthesis`, `marketDecisionSemantics`, `regimeSummary`, backend
  `researchReadiness`, provider health, and evidence snapshots
  (`src/services/market_overview_service.py:1105-1185`).
- Market temperature input assembly already consumes cached/internal snapshots
  for CN indices, breadth, flows, sector rotation, rates, volatility, macro,
  FX, futures, sentiment, crypto, Liquidity `capitalFlowSignal` /
  `officialMacroReadiness`, and Rotation `rotationFamilyRollup`
  (`src/services/market_overview_service.py:8370-8539`).
- Score-authority guards already reject proxy, fallback, unavailable, or
  provider-route-ineligible score inputs before temperature/briefing use them
  (`src/services/market_overview_service.py:8798-8870`,
  `src/services/market_overview_service.py:8919-8971`).
- Market temperature trust gating computes reliable input count, reliable panel
  count, coverage, confidence, `temperatureAvailable`, `conclusionAllowed`,
  `trustLevel`, `sourceTier`, `scoreCap`, and degradation reasons
  (`src/services/market_overview_service.py:9132-9253`).
- The backend currently projects temperature `researchReadiness` with required
  evidence limited to market-level metadata such as macro, liquidity, and
  technical context (`src/services/market_overview_service.py:1187-1277`).
- `market_decision_semantics.py` is already a pure, no-network, no-cache,
  no-provider-fanout foundation that derives observation-only posture,
  confidence, direction readiness, claim boundaries, confirmation signals,
  counter-evidence, and data gaps from already computed regime, liquidity, and
  rotation payloads (`src/services/market_decision_semantics.py:1-8`,
  `src/services/market_decision_semantics.py:185-290`).
- The shared `ResearchReadinessV1` helper is fail-closed and covers
  `ready`, `observe_only`, `insufficient`, `blocked`, and `waiting`, with
  source authority, freshness, missing evidence, no-advice boundaries, and
  next-evidence guidance (`src/services/research_readiness_contract.py:16-58`,
  `src/services/research_readiness_contract.py:202-260`).
- Scanner already has an additive top-down context adapter that consumes cached
  Market Temperature, cache-only Liquidity, and shared cached Rotation without
  changing scanner ranking or scoring (`src/services/market_scanner_context_adapter.py:46`).

### Frontend Paths

- Market Overview loads a broad panel set in staged and polling groups, including
  temperature and briefing as primary requests, then renders
  `ConsumerResearchReadinessStrip` above the main workbench
  (`apps/dsa-web/src/pages/MarketOverviewPage.tsx:56-142`,
  `apps/dsa-web/src/pages/MarketOverviewPage.tsx:914-929`).
- The frontend first tries `extractMarketResearchReadiness(panels.temperature)`,
  then falls back to `inferMarketResearchReadiness(panels.temperature)`
  (`apps/dsa-web/src/api/researchReadiness.ts:525-559`).
- Local inference maps `marketDecisionSemantics.directionReadiness` to
  `ResearchReadinessV1`, but it can only infer an observe-only/insufficient
  verdict and cannot represent the full backend contract with product-specific
  actionability guidance (`apps/dsa-web/src/api/researchReadiness.ts:561-593`).
- Market Overview also maintains a separate local four-state decision-readiness
  view (`ready`, `observe`, `unavailable`, `waiting`) for the top-surface
  decision layer (`apps/dsa-web/src/utils/marketIntelligenceGuidance.ts:9-21`,
  `apps/dsa-web/src/components/market-overview/MarketOverviewWorkbenchTopSurface.tsx:396-479`).
- The page already includes no-advice copy: "仅供研究观察，不构成交易指令"
  (`apps/dsa-web/src/components/market-overview/MarketOverviewWorkbenchTopSurface.tsx:808-810`).
- The current IA has a readable hierarchy but high density: L0 readiness strip,
  L1 decision semantics, L2 category/hero surface, L3 board plus side rail, and
  folded data/debug disclosures (`apps/dsa-web/src/components/market-overview/MarketOverviewWorkbenchTopSurface.tsx:780-837`,
  `apps/dsa-web/src/components/market-overview/MarketOverviewWorkbenchGrid.tsx:150-185`).

### Tests and Docs

- Backend tests already assert additive `marketDecisionSemantics`,
  `directionReadiness`, `researchReadiness`, no-advice boundaries, and degraded
  no-conclusion states for market temperature
  (`tests/api/test_market_temperature.py:478-547`,
  `tests/api/test_market_temperature.py:950-1028`).
- Market Intelligence payload smoke tests cover cache-only CN/HK flow,
  Liquidity proxy caps, funds-flow proxy wording, crypto sidecar observation
  state, and Rotation Radar fallback/read-only behavior
  (`tests/api/test_market_intelligence_payload_smoke.py:240-369`).
- The smoke checklist defines the protected backend cluster and requires
  degraded/fallback/stale/unavailable payloads not to appear live/fresh, Liquidity
  and Rotation proxy evidence not to be promoted, and Market Temperature /
  Briefing to fail closed when reliable inputs are missing
  (`docs/market-overview/market-intelligence-smoke-checklist.md:70-128`).
- The same checklist is explicitly advisory-only: these endpoints are not order
  intent and must not be used as evidence for scanner execution, backtest
  execution, portfolio mutation, broker/order flows, or auth/RBAC behavior
  (`docs/market-overview/market-intelligence-smoke-checklist.md:135-149`).
- Market Overview docs state that the first viewport should answer usability,
  partial/stale/unavailable state, and broad risk/rotation clues, while
  freshness/source detail belongs in a rail or disclosure
  (`docs/market-overview/README.md:20-47`).

## Why It Still Feels Unusable

1. The surface has a readiness strip, but no unified actionability path.
   Investors see "research readiness" plus a dense decision surface, category
   tabs, hero ribbon, board cards, rails, and disclosures. The product does not
   clearly sequence verdict -> confidence -> evidence coverage -> missing
   evidence -> next research step.

2. The backend verdict is too narrow. Current temperature readiness is attached
   to one payload and derives from a coarse set of market evidence. Rotation,
   Liquidity, Market Briefing, sector rotation, and scanner top-down context all
   affect the investor's understanding, but they do not feed a single Market
   Intelligence actionability envelope.

3. There are parallel frontend and backend readiness semantics. The shared
   `ResearchReadinessV1` states are `ready`, `observe_only`, `insufficient`,
   `blocked`, and `waiting`; the Market Overview top surface has a separate
   `ready`, `observe`, `unavailable`, `waiting` state model. That risks copy,
   severity, and fallback drift.

4. The current score is not the right answer. Market temperature scores,
   Rotation ranking, Liquidity scores, and Scanner ranks are valuable internal
   or surface-specific signals, but they are protected semantics. Treating any of
   them as a new consumer "actionability score" would blur source authority and
   create trading-advice risk.

5. The no-advice boundary exists, but the next research step is not first-class.
   The UI says not to treat the output as a trading instruction, but it does not
   consistently tell the user which evidence to collect next before trusting the
   market direction.

## Consumer-Safe Actionability Contract

The next contract should be additive and projection-only. Suggested name:
`marketActionabilityFrame` with `contractVersion:
market_intelligence_actionability_v1`.

Minimum fields:

```text
verdict:
  researchReadiness: ResearchReadinessV1
  actionabilityState: ready | observe_only | insufficient | blocked | waiting
  verdictLabel: controlled consumer copy
  confidence:
    label: high | medium | low | insufficient
    value: 0..1 optional, capped by source authority
    capReasons: bounded reason codes
evidenceCoverage:
  scoreGradeCount
  observationOnlyCount
  missingCount
  requiredDomains:
    macro
    liquidity
    breadth
    rotation
    source_authority
    freshness
missingEvidence:
  bounded evidence domains plus user-safe labels
regimeContext:
  primaryRegime
  liquidityImpulse
  rotationPosture
  contradictionCount
  freshnessFloor
researchPath:
  supportingEvidence
  counterEvidence
  nextResearchStep
  invalidationWatch
boundaries:
  consumerActionBoundary: no_advice
  noExecution: true
  noOrderPlacement: true
  noPortfolioMutation: true
debugRef:
  sanitized surface/payload id only, no raw payloads or secrets
```

State semantics:

- `ready`: research evidence is usable for a research note only; it is not a
  buy/sell/order signal and keeps `consumerActionBoundary=no_advice`.
- `observe_only`: evidence exists, but proxy, observation-only, partial,
  contradictory, or low-confidence inputs prevent stronger guidance.
- `insufficient`: required evidence, source authority, or freshness is missing.
- `blocked`: source authority or no-advice boundary is violated, or output would
  require protected-domain behavior changes.
- `waiting`: refresh or validation is in progress; do not upgrade conclusion
  until new evidence arrives.

Do not add execution-grade labels such as "tradeable", "buy", "sell", "order",
"best", "guaranteed", broker readiness, position sizing, or personalized
suitability.

## Reuse Plan Without Provider Fanout

The projection should consume existing outputs only:

- Market Overview / Temperature: `researchReadiness`,
  `marketDecisionSemantics.directionReadiness`, `marketRegimeSynthesis`,
  `regimeSummary`, trust fields, and `evidenceSnapshot`.
- Market Briefing: existing trust/cap/degraded narrative; do not create separate
  provider calls.
- Liquidity Monitor: `capitalFlowSignal`, `liquidityImpulseSynthesis`,
  `sourceMetadata`, indicator `coverageDiagnostics`, and proxy/score contribution
  gates.
- Rotation Radar / Sector Rotation: `rotationFamilyRollup`,
  `consumerEvidenceSnapshot`, `themeFlowSignal`, `rotationStateEvidence`,
  `rankingLane`, `headlineEligible`, `observationOnly`, and
  `scoreContributionAllowed`.
- Scanner: `scannerContextFrame` vocabulary for macro, liquidity, asset-class,
  theme, universe, and no-advice boundaries.
- Shared contract: `build_research_readiness_v1()` remains the verdict builder;
  Market Intelligence should not introduce a parallel verdict engine.

Implementation guardrails:

- No provider runtime order changes.
- No new providers or live-call paths.
- No MarketCache TTL/SWR/cold-start changes.
- No Rotation score, stage, headline ranking, or theme sorting changes.
- No Liquidity score/gate changes.
- No Scanner ranking, scoring, selection, thresholds, or sorting changes.
- No LLM prompt/model/routing changes.
- Additive API fields only; no breaking response shape changes.

## Frontend IA Gaps

Current hierarchy is present but not product-complete:

- L0 should be a single "Market research verdict" strip with state, confidence,
  evidence coverage, and next research step. Today L0 is only readiness, while
  actionability is split into local decision readiness and folded notes.
- L1 should answer "what can I research now?" Today it mixes market status,
  supporting evidence, data status, and local conclusion text.
- L2 should compare major context groups: macro, liquidity, breadth, rotation,
  risk assets, and missing evidence. Today these are spread across cards/tabs and
  side rails.
- L3 should hold details and diagnostics. Today admin-only debug is protected,
  but consumer disclosures still read as explanatory detail instead of a guided
  research checklist.

Consumer UI goals for T-933:

- Reuse `ConsumerResearchReadinessStrip` and, where appropriate, the evidence
  coverage vocabulary already used by Home and Scanner.
- Replace local Market Overview readiness copy with shared
  `ResearchReadinessV1` vocabulary.
- Keep provider/source/freshness internals in rail/disclosure, not the primary
  verdict.
- Keep raw reason codes, route diagnostics, source routers, provider payloads,
  prompts, stack traces, tokens, credentials, and session ids out of consumer UI.
- Add route-level smoke coverage that ordinary users do not see "技术细节",
  "原始原因代码", raw field names, or trading/action wording.

## Phased Write Tasks

### T-931 Market Intelligence Readiness/Verdict Contract

Goal: make `ResearchReadinessV1` the single consumer-safe verdict vocabulary for
Market Intelligence.

Suggested allowed final diff:

- `src/services/research_readiness_contract.py`
- `src/services/market_overview_service.py`
- `tests/api/test_market_temperature.py`
- `tests/services/test_research_readiness_contract.py`
- `docs/market-overview/README.md`
- `docs/CHANGELOG.md`

Implementation:

- Add or tighten a projection helper that maps existing Market Intelligence
  temperature/readiness metadata into `ResearchReadinessV1`.
- Ensure `blocked` and `waiting` are preserved when source authority, freshness,
  or no-advice boundaries require them.
- Keep fields additive and JSON-safe.
- Do not integrate new provider calls or change temperature score formulas.

Validation:

- Focused research readiness contract tests.
- `tests/api/test_market_temperature.py` degraded/ready/no-advice cases.
- `git diff --check` and secret scan.

### T-932 Market Intelligence Evidence Projection Backend

Goal: add additive `marketActionabilityFrame` from existing Market Overview,
Liquidity, Rotation, and Scanner/top-down metadata.

Suggested allowed final diff:

- `src/services/market_overview_service.py`
- `src/services/market_decision_semantics.py` if a pure projection mapper is
  needed
- `tests/api/test_market_temperature.py`
- `tests/api/test_market_briefing.py`
- `tests/api/test_market_intelligence_payload_smoke.py`
- `tests/test_market_intelligence_smoke_checklist.py`
- `docs/market-overview/market-intelligence-smoke-checklist.md`
- `docs/CHANGELOG.md`

Implementation:

- Build `marketActionabilityFrame` from existing payloads only.
- Include verdict, confidence, evidence coverage, missing evidence, regime
  context, no-advice boundary, next research step, supporting evidence,
  counter-evidence, and invalidation watch.
- Explicitly mark proxy/observation-only/fallback/stale/unavailable inputs as
  non-score-grade.
- Do not alter MarketCache, provider runtime, scoring, Rotation ranking,
  Liquidity scoring, Scanner behavior, or API breaking contracts.

Validation:

- Backend payload smoke for fallback, partial, proxy-only, and score-grade
  fixture paths.
- Assert no raw payload/provider/schema/debug leakage.
- Assert no buy/sell/order/trade/broker language.

### T-933 Market Intelligence Consumer UI Refinement

Goal: make Market Overview first viewport read as verdict -> confidence ->
evidence -> next research step, without card sprawl or trading advice.

Suggested allowed final diff:

- `apps/dsa-web/src/pages/MarketOverviewPage.tsx`
- `apps/dsa-web/src/components/market-overview/MarketOverviewWorkbenchTopSurface.tsx`
- `apps/dsa-web/src/components/market-overview/MarketOverviewWorkbench.tsx`
- `apps/dsa-web/src/api/researchReadiness.ts`
- `apps/dsa-web/src/api/market.ts`
- `apps/dsa-web/src/types/researchReadiness.ts`
- `apps/dsa-web/src/pages/__tests__/MarketOverviewPage.test.tsx`
- `apps/dsa-web/e2e/market-research-surfaces.spec.ts`
- `docs/CHANGELOG.md`

Implementation:

- Consume backend `ResearchReadinessV1` and `marketActionabilityFrame` as the
  source of truth.
- Retire or wrap the local four-state decision-readiness copy so it cannot drift
  from shared states.
- Keep L0/L1/L2/L3 compact: L0 verdict strip, L1 research path, L2 context
  groups, L3 disclosures/debug.
- Do not change data fetching behavior, routes, auth/RBAC, backend API calls,
  provider behavior, or runtime semantics.

Validation:

- Focused Vitest for ready/observe/insufficient/blocked/waiting rendering.
- Route smoke for no raw/internal terms and no trading language.
- Browser check for `/zh/market-overview` desktop/mobile no-overflow if UI is
  changed.

### T-934 Browser/API Contract Smoke

Goal: add acceptance coverage that the new contract remains consumer-safe and
does not affect protected domains.

Suggested allowed final diff:

- `tests/api/test_market_temperature.py`
- `tests/api/test_market_briefing.py`
- `tests/api/test_market_intelligence_payload_smoke.py`
- `apps/dsa-web/e2e/market-research-surfaces.spec.ts`
- `apps/dsa-web/e2e/market-overview-scanner.smoke.spec.ts`
- `docs/market-overview/market-intelligence-smoke-checklist.md`
- `docs/CHANGELOG.md`

Required assertions:

- `researchReadiness` / `marketActionabilityFrame` exist in happy, degraded,
  fallback, and partial payloads.
- Missing readiness fails closed.
- Proxy/fallback/stale/unavailable inputs do not become score-grade.
- Rotation observation/taxonomy themes stay out of headline lists.
- Scanner ranking/order/score fields are unchanged.
- Consumer route does not show raw provider payloads, route diagnostics, schema
  field names, stack traces, prompts, secrets, or raw session ids.
- Consumer route does not show forbidden trading language.

## Protected Domains Before Writes

Before any implementation, explicitly protect:

- provider runtime order, live-call paths, first-good-wins fallback, freshness
  labeling, raw payload handling, and MarketCache TTL/SWR/cold-start semantics
  (`docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md:77-94`);
- scanner scoring, candidate selection, thresholds, ranking/sorting, signal
  interpretation, and fallback/live labeling
  (`docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md:26-42`);
- Rotation score/stage/headline ranking and observation/taxonomy lane semantics;
- Liquidity score contribution, provider activation gates, and proxy caps;
- API response compatibility and stored contract versions;
- AI prompts, model routing, recommendation semantics, and evidence weighting
  (`docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md:95-109`);
- auth/RBAC/security, portfolio/accounting, backtest, broker/order, and
  notification behavior.

## Recommended Sequence

1. T-931 first: contract alignment. This removes readiness vocabulary drift and
   makes `ResearchReadinessV1` the only verdict language.
2. T-932 second: backend evidence projection. This adds the implementation-ready
   actionability frame without UI churn.
3. T-933 third: UI refinement. This consumes the stable contract and fixes IA.
4. T-934 fourth: browser/API smoke. This locks safety and protected-domain
   regressions after the contract and UI exist.

Do not start with UI-only polish. It would make the page look more decisive
without fixing the missing backend actionability envelope.

## No-Write Scope Confirmation

This audit intentionally did not edit runtime code, frontend TSX/CSS, backend
endpoint/service/provider/cache/storage/auth/accounting logic, LLM prompts,
provider routing, scanner/options/portfolio behavior, config, lockfiles, or CI.
It did not run provider probes or live calls, and it did not copy raw logs or
secrets into this document.
