# T-935 Options Lab Workflow IA Contract

Task ID: T-935
Mode: READ-ONLY-AUDIT
Scope: define the implementation-ready workflow IA contract for Options Lab productization, without changing runtime behavior.

## Executive Verdict

Options Lab already has the right raw ingredients: additive readiness aliases, fail-closed gates, no-trading boundaries, scenario/compare/decision DTOs, and consumer-safe browser coverage. The missing piece is not math or provider capability. The missing piece is the product contract that says how the surface should be read.

This audit defines that contract as a projection-only workflow:

```text
input selection -> chain quality -> readiness gates -> scenario evidence ->
strategy comparison -> decision-grade boundary -> next research step
```

The contract must stay additive and observational. It must not turn readiness into execution authority, and it must not widen protected runtime domains.

## Evidence Base

The current contract surface already exists in code:

- `OptionsResearchReadiness` and `OptionsNoTradingBoundary` are explicit schema types in `api/v1/schemas/options.py`.
- Summary, expirations, chain, analyze, scenario, strategy compare, and decision responses all populate both `optionsReadiness` and `optionsResearchReadiness` aliases.
- `optionsReadiness` / `optionsResearchReadiness` are treated as the same readiness record by current tests.
- `OptionsLabService` is fixture-backed and avoids live providers, LLMs, broker execution, and portfolio mutation.
- `OptionsLabPage` already renders readiness, comparison, decision, chain, risk boundary, and methodology surfaces.
- Backend decision labels can still include execution-adjacent strings such as `高风险，仅小仓验证` and `有条件可交易`; product UI and tests must keep those from becoming consumer execution copy.

Key references:

- `api/v1/schemas/options.py:230-250`
- `api/v1/schemas/options.py:549-596`
- `api/v1/schemas/options.py:649-811`
- `api/v1/schemas/options.py:947-1010`
- `src/services/options_lab_service.py:1-6`
- `src/services/options_lab_service.py:336-386`
- `src/services/options_lab_service.py:388-1942`
- `apps/dsa-web/src/pages/OptionsLabPage.tsx:781-1382`
- `apps/dsa-web/src/pages/OptionsLabPage.tsx:1458-1835`
- `apps/dsa-web/src/components/options/OptionsReadinessGateSummary.tsx:13-242`
- `apps/dsa-web/e2e/readiness-browser-acceptance.smoke.spec.ts:852-900`
- `tests/test_options_lab_service.py:146-170`
- `tests/test_options_lab_service.py:429-500`
- `tests/test_options_lab_service.py:1112-1155`
- `tests/api/test_options_lab.py:444-594`
- `tests/api/test_options_lab.py:46-90`
- `tests/api/test_options_lab.py:1216-1265`
- `tests/api/test_options_lab.py:2140-2170`

## Target Workflow

The product workflow must read in this order:

1. Input selection.
   - symbol
   - direction
   - target price
   - target date
   - risk budget
   - expiration
   - optional selected structure
2. Chain quality.
   - expiration exists
   - chain is present
   - bid/ask/mid coverage
   - volume and open interest coverage
   - IV and Greeks coverage
   - freshness and source labeling
3. Readiness gates.
   - provider authority
   - liquidity gate
   - IV/Greeks gate
   - spread gate
   - scenario coverage
   - no-trading boundary
4. Scenario evidence.
   - target move
   - breakeven pressure
   - max loss / max gain
   - expected move source
   - scenario payoff summary
5. Strategy comparison.
   - ordered candidate structures
   - top observation candidate
   - risk/reward summary
   - leg-level warnings only as supporting evidence
6. Decision-grade boundary.
   - decisionGrade true/false
   - research-ready vs blocked vs insufficient
   - still no execution authority
7. Next research step.
   - what evidence is missing
   - what should be checked next
   - never an execution action

## L0-L4 UI Hierarchy

The future product UI should follow the workflow above, while keeping deep detail collapsed by default.

| Layer | Purpose | Visible by default | Collapsed by default |
| --- | --- | --- | --- |
| L0 | Product verdict and boundary | route title, one-line verdict, readiness strip, 2-3 top blockers, freshness summary | raw reason codes, method notes, deep evidence |
| L1 | Input selection and chain quality summary | symbol, direction, target price/date, risk budget, expiration choice, chain quality summary | advanced assumptions, full chain rows, exhaustive diagnostics |
| L2 | Readiness gates and scenario evidence | gate chips, scenario coverage, breakeven pressure, max loss / max gain, expected move, selected/observed structure summary | leg diagnostics, raw gate issue lists, full contract rows |
| L3 | Strategy comparison and decision boundary | ordered candidate strategies, top candidate, decision boundary, next research step, no-trading copy | optimizer internals, full candidate list, raw fail-closed codes |
| L4 | Deep evidence and methodology | nothing should be forced visible here by default; only bounded disclosure entry points | call/put tables, methodology notes, limitation detail, row-level evidence |

Implementation note:

- The current page already shows deeper evidence earlier than this contract wants.
- T-937 should move chain detail and method detail deeper, while keeping the main path readiness-first.
- T-937 must make the L1 interaction contract explicit: either assumptions auto-preview the scenario, or the user explicitly submits with "refresh scenario"; do not keep both semantics ambiguous.
- The visual contract must make the workflow legible even on mobile without horizontal overflow.

## `OptionsProductReadinessV1`

This contract should be an additive wrapper over the existing readiness record, not a second gate system.

### Required top-level fields

| Field | Type | Required | Source / meaning |
| --- | --- | --- | --- |
| `contractVersion` | string literal | yes | version tag for the product contract, e.g. `options-product-readiness-v1` |
| `subject` | object | yes | symbol/market/as-of context for the current surface |
| `readiness` | object | yes | the existing `OptionsResearchReadiness` record, preserved as the canonical readiness core |
| `chainQuality` | object | yes | chain presence, coverage, freshness, and quality summary |
| `providerEvidence` | object | yes | safe provider authority and data-source summary |
| `gateSummary` | object | yes | compact gate/result summary for the product surface |
| `boundary` | object | yes | the no-trading / no-execution / no-portfolio-mutation boundary |
| `blockingReasons` | string[] | yes | deduped reasons that explain why the surface is blocked or limited |
| `missingEvidence` | string[] | yes | consumer-safe labels for missing evidence classes |
| `nextEvidenceNeeded` | string[] | yes | next research checks, not execution steps |

### `subject`

| Field | Type | Required | Source / meaning |
| --- | --- | --- | --- |
| `symbol` | string | yes | selected underlying symbol |
| `market` | string | yes | market code or market family |
| `asOf` | string \| null | recommended | current snapshot timestamp if available |
| `sourceLabel` | string \| null | recommended | safe source label for the current snapshot |

### `readiness`

Use the existing readiness record as-is:

- `optionsResearchReady`
- `readinessState`
- `dataQualityTier`
- `decisionGrade`
- `providerAuthority`
- `liquidityGate`
- `ivGreeksGate`
- `spreadGate`
- `scenarioCoverage`
- `noTradingBoundary`

No alias divergence is allowed. `optionsReadiness` and `optionsResearchReadiness` are the same record in practice and must remain compatible.

### `chainQuality`

| Field | Type | Required | Source / meaning |
| --- | --- | --- | --- |
| `expirationCount` | number | recommended | number of expirations seen |
| `contractCount` | number | recommended | total contracts in the active chain |
| `callCount` | number | recommended | call rows present |
| `putCount` | number | recommended | put rows present |
| `hasBidAskCoverage` | boolean | recommended | bid/ask coverage is present |
| `hasIvCoverage` | boolean | recommended | IV coverage is present |
| `hasGreeksCoverage` | boolean | recommended | Greeks coverage is present |
| `freshness` | string | recommended | freshness label from the source payload |
| `sourceType` | string | recommended | sanitized source type, not raw provider payload |
| `coverageState` | string | recommended | e.g. missing, partial, single_contract, compare_ready |

### `providerEvidence`

| Field | Type | Required | Source / meaning |
| --- | --- | --- | --- |
| `providerName` | string | recommended | safe provider name |
| `liveProviderEnabled` | boolean | recommended | whether live provider support is enabled |
| `sourceType` | string | recommended | safe source-type label |
| `authorityTier` | string | recommended | score-grade / observation-only / unavailable style label |
| `tradeableData` | boolean \| null | recommended | whether the provider claims tradeable data is available |
| `decisionReady` | boolean \| null | recommended | safe summary of decision readiness |
| `analysisReady` | boolean \| null | recommended | safe summary of analysis readiness |
| `reasonCodes` | string[] | recommended | sanitized reason codes only |

Do not expose raw `providerCapabilities` wholesale in this contract. Keep only safe summaries.

### `gateSummary`

| Field | Type | Required | Source / meaning |
| --- | --- | --- | --- |
| `gateDecision` | string | recommended | blocked / observe_only / manual_review / clear style summary |
| `issueCount` | number | recommended | compact count of gate issues |
| `legCount` | number | recommended | count of included legs/structures if present |
| `failClosedReasonCodes` | string[] | recommended | existing fail-closed reason codes when present |

## `OptionsConsumerScenarioFrame`

This contract is the consumer-facing scenario view. It should not become a second readiness system.

### Required top-level fields

| Field | Type | Required | Source / meaning |
| --- | --- | --- | --- |
| `contractVersion` | string literal | yes | version tag for the scenario frame |
| `subject` | object | yes | symbol/market/as-of context |
| `scenarioInput` | object | yes | user inputs and assumptions |
| `structureFrame` | object | yes | selected or observed option structure summary |
| `chainQualitySummary` | object | yes | chain quality summary for the active scenario |
| `liquidityFrame` | object | yes | liquidity and spread evidence |
| `ivGreeksFrame` | object | yes | IV/Greeks evidence |
| `scenarioEvidence` | object | yes | target move, breakeven, payoff, and expected move summary |
| `comparisonFrame` | object | yes | strategy comparison summary |
| `decisionBoundary` | object | yes | decision-grade boundary and no-trading boundary |
| `nextResearchStep` | object | yes | next evidence needed and user-safe next step |

### `scenarioInput`

| Field | Type | Required | Source / meaning |
| --- | --- | --- | --- |
| `direction` | string | yes | bullish / bearish / neutral / volatility |
| `targetPrice` | number | recommended | scenario target price |
| `targetDate` | string | recommended | scenario target date |
| `riskBudget` | number \| null | recommended | user risk budget |
| `expiration` | string \| null | recommended | selected expiration |
| `holdingHorizonDays` | number \| null | optional | if the page exposes a horizon |
| `selectedStrategyType` | string \| null | recommended | explicit user-selected strategy, if any |
| `structureSelectionState` | string | yes | `selected`, `observed`, `auto_preview`, or `none` style state |

### `structureFrame`

| Field | Type | Required | Source / meaning |
| --- | --- | --- | --- |
| `selectedStructure` | object \| null | recommended | explicit structure chosen by the user |
| `observedStructure` | object \| null | recommended | the top observation candidate if no structure is selected |
| `premiumAtRisk` | number \| null | recommended | premium at risk summary |
| `maxLoss` | number \| null | recommended | max loss summary |
| `maxGain` | number \| null | recommended | max gain summary |
| `breakeven` | number \| null | recommended | breakeven summary |
| `requiredMovePct` | number \| null | recommended | required move summary |

### `chainQualitySummary`

| Field | Type | Required | Source / meaning |
| --- | --- | --- | --- |
| `hasChain` | boolean | yes | whether the active chain exists |
| `expirationCount` | number | recommended | number of expirations in scope |
| `contractCount` | number | recommended | number of contracts in scope |
| `callCount` | number | recommended | count of call rows |
| `putCount` | number | recommended | count of put rows |
| `freshness` | string | recommended | safe freshness label |
| `sourceType` | string | recommended | safe source type |

### `liquidityFrame`

| Field | Type | Required | Source / meaning |
| --- | --- | --- | --- |
| `liquidityGate` | string | yes | current liquidity gate |
| `spreadGate` | string | yes | current spread gate |
| `spreadPct` | number \| null | recommended | active spread summary |
| `liquidityWarnings` | string[] | recommended | safe warning labels |
| `volume` | number \| null | optional | active volume summary |
| `openInterest` | number \| null | optional | active open interest summary |

### `ivGreeksFrame`

| Field | Type | Required | Source / meaning |
| --- | --- | --- | --- |
| `ivGreeksGate` | string | yes | current IV/Greeks gate |
| `ivRankStatus` | string | recommended | IV rank availability |
| `ivRank` | number \| null | optional | safe IV rank summary |
| `ivPercentile` | number \| null | optional | safe IV percentile summary |
| `ivRankConfidence` | string \| null | optional | confidence label |
| `warnings` | string[] | recommended | safe warning labels |

### `scenarioEvidence`

| Field | Type | Required | Source / meaning |
| --- | --- | --- | --- |
| `expectedMoveAbs` | number \| null | recommended | expected move in price units |
| `expectedMovePct` | number \| null | recommended | expected move in percentage units |
| `expectedMoveSource` | string | recommended | safe source label |
| `payoffAtTarget` | number \| null | recommended | payoff at the user target |
| `targetPriceStatus` | string | recommended | status of the target price input |
| `scenarioCoverage` | string | yes | scenario coverage summary |

### `comparisonFrame`

| Field | Type | Required | Source / meaning |
| --- | --- | --- | --- |
| `candidateCount` | number | recommended | number of strategies compared |
| `topStrategyType` | string \| null | recommended | top observation candidate strategy |
| `orderedStrategies` | object[] | recommended | safe ranked list, not an execution recommendation |
| `riskRewardSummary` | object \| null | recommended | compact risk/reward summary |
| `primaryReasons` | string[] | recommended | safe reason labels |

### `decisionBoundary`

| Field | Type | Required | Source / meaning |
| --- | --- | --- | --- |
| `readinessState` | string | yes | readiness state for the current surface |
| `dataQualityTier` | string | yes | data-quality tier |
| `decisionGrade` | boolean | yes | research-grade yes/no |
| `providerAuthority` | string | yes | provider authority summary |
| `noTradingBoundary` | object | yes | the no-trading boundary |
| `boundaryCopy` | string | yes | safe consumer copy only |

### `nextResearchStep`

| Field | Type | Required | Source / meaning |
| --- | --- | --- | --- |
| `blockingReasons` | string[] | yes | safe blocker labels |
| `nextEvidenceNeeded` | string[] | yes | next research checks |
| `consumerActionLabel` | string | yes | safe next-step label such as `仅观察` or `等待证据更新` |

## Mapping From Existing `optionsReadiness` / `optionsResearchReadiness`

The current aliases should continue to map into the new product IA as follows:

| Existing payload source | Product contract mapping | Notes |
| --- | --- | --- |
| `OptionUnderlyingSummaryResponse.optionsReadiness` / `.optionsResearchReadiness` | `OptionsProductReadinessV1.readiness` | same record, same semantics |
| `OptionExpirationsResponse.optionsReadiness` / `.optionsResearchReadiness` | `OptionsProductReadinessV1.readiness` | same record, same semantics |
| `OptionChainResponse.optionsReadiness` / `.optionsResearchReadiness` | `OptionsProductReadinessV1.readiness` + `chainQuality` | chain detail feeds the product summary |
| `OptionsAnalyzeResponse.optionsReadiness` / `.optionsResearchReadiness` | readiness + `comparisonFrame` precursor | analysis payload informs candidate structure context |
| `OptionsScenarioResponse.optionsReadiness` / `.optionsResearchReadiness` | readiness + `scenarioEvidence` + `structureFrame` | scenario endpoint is the cleanest evidence seam |
| `OptionsStrategyCompareResponse.optionsReadiness` / `.optionsResearchReadiness` | readiness + `comparisonFrame` | compare is an observation artifact, not a selected trade |
| `OptionsDecisionResponse.optionsReadiness` / `.optionsResearchReadiness` | readiness + `decisionBoundary` + `nextResearchStep` | decision payload should not become execution authority |

Mapping rule:

- `optionsReadiness` is the legacy alias.
- `optionsResearchReadiness` is the canonical alias for consumer code.
- They must remain equal.
- Neither alias may imply broker execution or portfolio mutation.

## No-Trading / No-Execution / No-Portfolio-Mutation Boundary

Keep the boundary explicit and visible:

- `只读观察`
- `研究就绪`
- `仅观察`
- `证据不足`
- `等待证据更新`
- `不构成买卖建议`
- `不会提交订单`
- `不连接经纪商`
- `不改动投资组合`
- `不可用于真实交易判断`

Do not introduce execution-flavored product copy such as:

- `trade quality`
- `决策实验室`
- `可成交性`
- `有条件可交易`
- `买入`
- `卖出`
- `下单`
- `立即交易`
- `稳赚`
- `保证收益`
- `AI recommends you buy`

This boundary applies even when `decisionGrade` is true. In this product, `decisionGrade` means "research-grade observation is available", not "the user should trade".

Backend output labels that are kept for older service/API semantics must be translated before they reach the consumer IA. In particular, `高风险，仅小仓验证` and `有条件可交易` must map to observation-only product copy such as `仅观察`, `研究结论受限`, or `等待证据更新`.

## Protected Domains

Do not change these domains in T-935 or its follow-up writes:

- strategy math and payoff math
- Greeks and IV assumptions
- provider authority semantics
- provider order, live-call paths, fallback, and cache semantics
- broker, order, execution, account, and portfolio mutation
- portfolio accounting, cash, holdings, P&L, sync, import, replay, FX, and cost basis
- AI/LLM prompts, model routing, and recommendation semantics
- auth/RBAC/security
- API response shape or stored contract versioning except additive projection fields in explicitly allowed files

The current backend guard already classifies these as protected. Productization must stay on the projection side of those boundaries.

## Required Tests Before Productization Writes

Before any T-936/T-937/T-938 write task, the new contract should be guarded by the existing test surfaces below.

### API / service

- `tests/api/test_options_lab.py`
  - alias compatibility
  - no raw provider / secret / live-path leakage
  - no broker / order / portfolio mutation imports or calls
  - execution-adjacent label suppression for `有条件可交易` and similar strings
  - readiness fail-closed states
  - delayed vs live readiness distinction
  - missing chain / selected legs / bid-ask / IV / Greeks / OI / volume / provider authority states
- `tests/test_options_lab_service.py`
  - scenario determinism
  - compare and decision flows
  - no external calls
  - no mutation paths
  - safe no-advice boundaries

### Frontend API / page

- `apps/dsa-web/src/api/__tests__/optionsLab.test.ts`
  - typed DTO compatibility
  - scenario client shape once introduced
  - sanitized fallback behavior
  - execution-adjacent backend labels mapped into safe consumer labels
- `apps/dsa-web/src/pages/__tests__/OptionsLabPage.test.tsx`
  - L0-L4 ordering
  - readiness-first summary
  - scenario evidence projection
  - source-of-truth for the selected structure
  - explicit refresh vs auto-preview behavior
  - no raw/internal leakage
  - no execution wording
- `apps/dsa-web/src/pages/tests/OptionsLabPage.test.tsx`
  - visible copy sentinels for analytical/no-decision wording

### Browser smoke

- `apps/dsa-web/e2e/readiness-browser-acceptance.smoke.spec.ts`
  - readiness strip visible
  - no horizontal overflow
  - no raw/internal leakage
  - no forbidden trading wording
  - desktop and mobile fail-closed behavior for missing/partial/malformed payloads
- `apps/dsa-web/e2e/no-secret-critical-surface.smoke.spec.ts`
  - secret-free, diagnostic-free consumer surface

### Validation gate before the write tasks land

- `git diff --check`
- `./scripts/release_secret_scan.sh`
- focused API/service/UI/browser smoke relevant to the follow-up task

## Next Write Tasks

Recommended sequence:

1. T-936: add the scenario evidence projection and typed contract seam.
2. T-937: refine the consumer UI around the new projection and make the refresh / recompute contract explicit.
3. T-938: add browser/API smoke that proves the workflow is safe and non-execution-grade.

If a later branch already consumes one of those ticket numbers, renumber the whole trio together to preserve order. Do not split the sequence across unrelated ticket IDs.

## Audit Closeout

This audit does not change runtime code.

No backend endpoint, service, provider, cache, storage, auth, accounting, math, or frontend TSX/CSS behavior was edited.

The resulting contract is ready for bounded follow-up writes.
