# T-892 Research OS Product Gap Audit

Task ID: T-892-GOAL
Mode: CODEX-ISOLATED
Scope: docs-only product architecture audit. No runtime code was changed by this
task.

## Executive Verdict

The core gap is not that WolfyStock lacks provider controls, fallback metadata,
or low-level data-quality gates. Those controls already exist in several places.
The gap is that the product does not yet expose one unified consumer-facing
`research_ready` verdict across Home AI, Market Intelligence, Scanner, Options
Lab, and Admin/Ops.

Current lower layers can record source tiers, freshness, trust levels, score
caps, observation-only flags, missing evidence, budget skips, and provider
diagnostics. The user-facing product still lets a result-bearing analysis finish
as `success` or `completed`, while the strongest consumer message may still be a
stock score, action label, shortlist rank, or local market direction phrase.
WolfyStock should become a research OS by promoting evidence readiness into the
first-class product contract, not by widening provider calls or adding trading
language.

## Evidence Summary

- Home AI builds rich `data_quality_report` and runtime summaries before the LLM
  call, then applies score caps and unsafe-text neutralization after the LLM
  returns. See `src/core/pipeline.py:923-1024` and
  `src/core/pipeline.py:1168-1318`.
- The analyzer can retry missing required fields, but after retries it can fill
  placeholders and continue. See `src/analyzer.py:82-149` and
  `src/analyzer.py:1290-1348`.
- The public analysis response carries missing domains and confidence caps, but
  it still centers `decision`, `action`, `score`, and `confidence`. See
  `src/services/analysis_service.py:283-391`.
- Async tasks mark any non-empty analysis result as `completed`; guest preview
  logs `overall_status="success"`. See `src/services/task_queue.py:954-1094`
  and `api/v1/endpoints/analysis.py:300-318`.
- Provider metadata is explicitly inert and captures domains, markets, quota,
  freshness, scanner usage, TTLs, and risk notes. See
  `src/services/provider_capability_matrix.py:1-130`.
- The provider planner already separates US and CN categories, timeouts, TTLs,
  max attempts, and budget skips. See
  `src/services/analysis_provider_planner.py:161-219` and
  `src/services/analysis_provider_planner.py:293-393`.
- Scanner already has controlled profiles, shortlist views, explainability, and
  diagnostics, but it is a discovery pipeline, not a top-down investor workflow.
  See `docs/market-scanner.md:33-57`, `docs/market-scanner.md:151-188`,
  `docs/market-scanner.md:221-248`, and `docs/market-scanner.md:266-288`.
- Market Intelligence already has local readiness concepts and strict degraded
  state rules, but no cross-surface research OS verdict. See
  `apps/dsa-web/src/utils/marketIntelligenceGuidance.ts:1-70`,
  `apps/dsa-web/src/utils/marketIntelligenceGuidance.ts:348-462`,
  `docs/market-overview/market-intelligence-smoke-checklist.md:65-136`, and
  `src/services/market_overview_service.py:9128-9160`.
- Options Lab already preserves hard no-trading and fail-closed metadata, but
  remains fixture/demo or readiness-lab grade until live authority, liquidity,
  IV, Greeks, OI, and spread quality are validated. See
  `api/v1/schemas/options.py:20-92`, `api/v1/schemas/options.py:320-452`,
  `src/services/options_lab_service.py:1464-1515`, and
  `tests/api/test_options_lab.py:1220-1254`.
- Admin/Ops has multiple gated routes and strong redaction rules, but the
  information architecture is page-sprawled instead of grouped by operator
  decision level. See `apps/dsa-web/src/App.tsx:389-425`,
  `docs/admin-ops/README.md:1-31`,
  `docs/design/wolfystock-market-provider-operations-dashboard.md:11-78`, and
  `docs/audits/admin-data-control-center-design.md:148-160`.

## 1. Home AI Data Flow And Fail-Open Product Gap

### Current Flow

1. Request entry
   - `POST /api/v1/analysis/analyze` accepts sync or async analysis and submits
     async jobs through the task queue. The async path preserves report type,
     force refresh, research mode, and owner metadata before submission
     (`api/v1/endpoints/analysis.py:469-503`).
   - Guest preview creates an execution log, runs `AnalysisService.analyze_stock`
     synchronously, then hides deep detail from the preview response
     (`api/v1/endpoints/analysis.py:220-299`).

2. Provider and context assembly
   - The analysis provider plan chooses different category chains for US vs CN
     symbols. US uses FMP, yfinance, Finnhub, Alpha Vantage, GNews, Tavily,
     Alpaca; CN uses AkShare, Tushare, pytdx, Baostock, efinance, static
     mapping, GNews, Tavily, and local inference
     (`src/services/analysis_provider_planner.py:161-185`).
   - The single-stock pipeline gathers realtime quote, fundamentals, earnings,
     historical prices, technical indicators, news, sentiment, and diagnostics,
     then builds multidimensional context and a `data_quality_report`
     (`src/core/pipeline.py:923-967`).
   - The current single-stock runtime only wires selected provider categories in
     the fast plan: quote, fundamentals, earnings, historical prices, and
     technical indicators (`src/core/pipeline.py:1100-1128`). News and sentiment
     still participate elsewhere, but they are not represented as a single
     consumer-ready research packet with blocking semantics.

3. LLM prompt and extraction
   - The analyzer includes data-quality summary fields such as
     `dataQualityTier`, `requiredAvailable`, `confidenceCap`, stale sources,
     provider timeouts, missing fields, warnings, and fallback flags in prompt
     context (`src/analyzer.py:1458-1528`).
   - The analyzer parses the LLM response into `AnalysisResult`, can retry
     integrity gaps, and then logs completion when a result exists
     (`src/analyzer.py:1290-1348`).

4. Fallback and partial handling
   - Missing mandatory fields are detected by `check_content_integrity`
     (`src/analyzer.py:82-113`).
   - If retries are exhausted, `apply_placeholder_fill` can fill missing score,
     advice, summary, core conclusion, risk alerts, or stop loss instead of
     failing the flow (`src/analyzer.py:116-149`).
   - After the LLM result exists, data-quality caps can set
     `decision_type="data_insufficient"`, replace unsafe action text with
     `data insufficient`, mark sniper points ungrounded, attach
     `score_authenticity`, and cap confidence (`src/core/pipeline.py:1168-1318`).

5. Public serialization and completion
   - The response payload carries `score_state`, `missing_required_domains`,
     `confidence_cap`, and `dataQualityReport`, but the main result object still
     exposes `decision`, `action`, `score`, `confidence`, and strategy fields
     (`src/services/analysis_service.py:283-391`).
   - Async task completion is result-based: if `AnalysisService.analyze_stock`
     returns a dict, `_mark_task_completed` sets task status to `COMPLETED`,
     progress to 100, message to "analysis complete", and logs
     `overall_status="completed"` (`src/services/task_queue.py:954-1094`).
   - Guest preview logs `overall_status="success"` and finishes the execution
     as `success` whenever a response is built (`api/v1/endpoints/analysis.py:300-318`).

### Why ORCL Could Produce Weak Detail

ORCL weakness is consistent with the product contract above:

- weak or missing inputs can be detected and passed into the prompt;
- the analyzer can still return an object after placeholder fill or low-quality
  caps;
- the API/task layer can still present the run as successful because the task
  lifecycle status is based on result presence, not on a top-level
  research-readiness verdict;
- the final consumer sees a decision-shaped response even when the correct
  product posture should be "not research-ready, here is what is missing".

This is a product fail-open gap. The lower layers often degrade correctly, but
the product lacks a single first-class verdict that blocks over-interpretation.

### Required Contract

Introduce an additive `ResearchReadinessV1` projection that every consumer
surface can show before any score, action, shortlist, or market direction.

Minimum fields:

```text
researchReady: boolean
readinessState: ready | observe_only | insufficient | blocked | waiting
verdictLabel: controlled consumer copy
blockingReasons: bounded reason codes
missingEvidence: technical | fundamentals | news | catalyst | macro | liquidity | source_authority | freshness
evidenceCoverage: score-grade count, observation-only count, missing count
sourceAuthority: scoreGradeAllowed | observationOnly | unavailable
freshnessFloor: fresh | delayed | stale | synthetic | fallback | unknown
consumerActionBoundary: no_advice | no_execution | no_trade | observe_only
nextEvidenceNeeded: short ordered list
debugRef: sanitized log/report path or execution id
```

This should be projection-only at first. It must not change provider order, LLM
prompt semantics, scoring thresholds, cache behavior, or task lifecycle until a
separate implementation Goal explicitly scopes those changes.

## 2. Source Utilization Map

The current source picture is mature enough for a research OS, but it needs a
clean product projection. The table below separates best use from decision
authority.

| Source | Current use | Best use | Gaps / limits | Consumer-safe projection |
| --- | --- | --- | --- | --- |
| Alpha Vantage | Fundamentals, earnings, and technical fallback in analysis (`src/core/pipeline.py:1113-1128`). | Deep/manual fundamentals and technical reference. | Scarce quota, manual-review freshness, rejected for scanner scoring and live quotes (`src/services/provider_capability_matrix.py:1490-1517`). | `observation_only` unless explicitly used as cached deep-research evidence. |
| Finnhub | US quote, fundamentals metrics, news fallback (`src/core/pipeline.py:1104-1112`). | Bounded quote enrichment, company news reference. | Key required, plan dependent, not for scanner fanout or live Market Overview (`src/services/provider_capability_matrix.py:1593-1608`). | Show source, plan-dependent freshness, and fallback status; no score authority by default. |
| Yahoo / yfinance | Quote/OHLCV/fundamental fallback; broad cheap baseline (`src/services/provider_capability_matrix.py:232-248`). | Cheap delayed research cross-check and fallback. | Unofficial, often delayed, not decision-grade live data (`src/services/provider_capability_matrix.py:247-248`; `src/services/provider_capability_matrix.py:1935-1950`). | `weak_public_proxy`, delayed/fallback disclosure, score contribution blocked unless reviewed. |
| Alpaca | US quote/OHLCV capability, preferred quote chain candidate (`src/services/provider_capability_matrix.py:274-290`; `src/services/analysis_provider_planner.py:165`). | Configured US quote/OHLCV enrichment after preselection. | Entitlement and feed affect realtime vs delayed posture (`src/services/provider_capability_matrix.py:289-290`). | `source_authority_pending_entitlement`, not broad scanner-wide research. |
| Twelve Data | HK/US quote/OHLCV, forex, crypto capability (`src/services/provider_capability_matrix.py:293-309`). | HK/US quote reference, FX/crypto cross-check. | Scarce quota, key required, not for scanner fanout or Market Overview runtime (`src/services/provider_capability_matrix.py:1903-1918`). | Bounded enrichment only; show quota and plan-dependent freshness. |
| FMP | US quote, OHLCV, fundamentals, statements, earnings, technicals (`src/services/provider_capability_matrix.py:312-349`). | First-line US fundamentals/statements and bounded earnings. | Avoid quota burn on broad OHLCV or external technicals when local data works (`src/services/provider_capability_matrix.py:348-349`). | `score_candidate` only for specific fields after coverage/freshness gates. |
| GNews | News chain candidate for US/CN (`src/services/analysis_provider_planner.py:170-182`). | Explicit top-N research enrichment. | Scarce quota, not scanner-wide, not quick analysis (`src/services/provider_capability_matrix.py:390-407`). | `news_observation`, cite timeout/fallback, never block scanner unless Goal scopes it. |
| FRED | Official macro baseline and Fed liquidity reference (`src/services/provider_capability_matrix.py:1611-1657`). | Official public macro context and cache-backed regime evidence. | Daily/weekly release lag, not intraday scoring, score-grade only when official cache is complete. | `official_public`, release-lag freshness, observation until readiness eligible. |
| US Treasury | Official rate reference and macro baseline cross-check (`src/services/provider_capability_matrix.py:1871-1885`). | Official public rates and yield context. | Daily release cadence, not intraday rates or premarket. | `official_public`, delayed release cadence, cache-safe macro input. |
| AkShare | CN/HK quote/OHLCV/technicals and CN observation (`src/services/provider_capability_matrix.py:251-271`). | CN/HK observation-first enrichment and fallback. | Public web interfaces can change, not official or decision-grade live data (`src/services/provider_capability_matrix.py:266-271`). | `weak_public_proxy`, visible degradation reason, no source-authority promotion. |
| pytdx | CN quote observation / baseline health reference (`src/services/provider_capability_matrix.py:1826-1840`). | CN quote observation and provider health reference. | Unofficial public API, not official quotes or score inputs. | `usable_with_caution` when healthy, but `scoreContributionAllowed=false` per Market Overview rules (`docs/market-overview/market-intelligence-smoke-checklist.md:118-124`). |
| Tushare Pro | A-share delayed observation and CN reference enrichment (`src/services/provider_capability_matrix.py:1886-1901`). | Gated CN reference enrichment when configured. | Paid/key required, plan dependent, not provider-order changes or live CN/HK flows. | `gated_public_api`, show key/config state, no default live panel authority. |

Important implementation principle: provider capability and data-source route
diagnostics already serialize `sourceTier`, `trustLevel`, `freshnessExpectation`,
`observationOnly`, `scoreContributionAllowed`, key requirements, and missing
provider reasons without calling provider runtimes or networks
(`src/services/data_source_router_diagnostics.py:1-92`). Reuse this vocabulary
instead of inventing new provider labels.

## 3. Top-Down Investor Workflow Contract

Scanner should stop being perceived as "run a screener and then ask AI to
explain candidates". It should become the execution lane of a top-down research
workflow:

```text
global regime and liquidity
-> asset classes
-> sector/theme and style tilts
-> industries
-> candidate stocks
-> fundamentals, technicals, catalyst, risk
-> execution-readiness boundary
```

### Required Inputs

1. Global regime and liquidity
   - Market Overview `marketRegimeSynthesis`, Market Temperature, Market
     Briefing, Liquidity Monitor official macro readiness, USD pressure, rates,
     bonds, gold, crypto, and breadth.
   - Inputs must carry readiness and source-authority metadata before they can
     influence scanner context.

2. Asset class frame
   - Equities, rates/bonds, gold, crypto, USD, and cash/liquidity pressure.
   - This frame should produce `risk_on`, `risk_off`, `mixed`, or
     `data_insufficient`, not a buy/sell instruction.

3. Sector/theme frame
   - Existing Rotation Radar and Sector Rotation can supply themes, but
     fallback/static themes must remain observation-only and out of headline
     ranking (`docs/market-overview/market-intelligence-smoke-checklist.md:90-94`).

4. Industry and candidate stocks
   - Scanner profiles already provide market-specific shortlist workflows and
     controlled universes (`docs/market-scanner.md:33-57`).
   - Candidate rows already include rank, final score, raw score, quality hints,
     reasons, metrics, feature signals, and risk notes
     (`docs/market-scanner.md:177-188`).

5. Fundamental, technical, catalyst, risk, and execution-readiness
   - Home AI can perform the single-name deep dive, but it must accept upstream
     readiness metadata and return `researchReady=false` when required evidence
     is missing.
   - Execution-readiness must mean "sufficient analytical evidence for a
     research note", not order placement.

### Scanner Product Contract

Add a `scannerContextFrame` next to each run:

```text
marketReadiness: ResearchReadinessV1
macroRegime: source, freshness, confidence, blockers
liquidityFrame: source, observationOnly, scoreContributionAllowed
assetClassBias: observe_only | ready | blocked
themeFrame: themes, proxyOnly, observationOnly
universePolicy: default | theme | symbols, bounded reason
candidateReadiness: per-candidate ResearchReadinessV1
noAdviceBoundary: true
```

Scanner AI should remain a translation layer. Existing docs already say it does
not replace rank/score, does not become first-round selection, does not block
Scanner, and does not output trading or execution instructions
(`docs/market-scanner.md:221-248`).

## 4. Market Intelligence Audit

Market Intelligence is the strongest current template for the future research
OS. It already has:

- decision readiness labels: ready, observe, unavailable, waiting
  (`apps/dsa-web/src/utils/marketIntelligenceGuidance.ts:1-70`);
- insufficient-evidence logic tied to `conclusionAllowed`,
  `temperatureAvailable`, `isReliable`, low confidence, missing pillars, and
  data gaps (`apps/dsa-web/src/utils/marketIntelligenceGuidance.ts:348-397`);
- support, blocking, and watch drivers for user-facing guidance
  (`apps/dsa-web/src/utils/marketIntelligenceGuidance.ts:400-462`);
- backend trust fields that cap stale/fallback/unavailable evidence before
  strong conclusions: `trustLevel`, `sourceTier`, `degradationReasons`,
  `scoreCap`, and `conclusionAllowed`
  (`src/services/market_overview_service.py:9128-9160`);
- explicit smoke-check rules that degraded data must not appear live/fresh and
  Market Temperature/Briefing must not emit strong bullish/bearish language
  from fallback-only inputs
  (`docs/market-overview/market-intelligence-smoke-checklist.md:65-136`).

The missing product piece is a unified research-grade verdict:

- Market Intelligence can say "direction-ready" locally, but Home AI, Scanner,
  Options, and Watchlist do not consume the same contract.
- Current copy still risks reading as a market direction summary rather than a
  research-readiness gate.
- It does not define a shared `researchReady=false` object that downstream
  Scanner and Home AI must respect.

### Proposed Research-Readiness Scoring

Use evidence gates, not investment advice:

| Pillar | Score contribution | Blocker examples |
| --- | --- | --- |
| Source authority | Only score-grade official or authorized sources can unlock strong conclusions. | proxy-only, unofficial, stale, synthetic |
| Freshness | Must meet surface-specific freshness floor. | stale, delayed beyond policy, fallback snapshot |
| Coverage | Required panels or evidence classes must be present. | missing macro, missing liquidity, missing breadth |
| Contradiction | Counter-evidence limits verdict strength. | mixed regime, liquidity vs breadth conflict |
| Downstream safety | Consumer surface must expose no-advice boundary. | buy/sell wording, execution CTA, ungrounded entry |

Verdict states:

```text
ready: enough evidence for a research note
observe_only: useful context, not enough for a directional verdict
insufficient: missing required evidence
blocked: safety or authority gate blocks conclusion
waiting: data/process pending
```

## 5. Options Lab Product-Readiness Audit

Options Lab is correctly constrained as a readiness lab, not a trading surface.
Existing schema exposes no-order, no-broker, no-portfolio-mutation, no-trading,
fixture, synthetic, no-external-calls, and no-LLM metadata
(`api/v1/schemas/options.py:20-46`). Contract rows include bid/ask/mid,
volume, open interest, IV, Greeks, spread percent, liquidity bucket, source,
freshness, provider quality, and data quality
(`api/v1/schemas/options.py:58-92`). Decision responses expose data quality,
liquidity, IV/Greeks readiness, expected move, gate issues, and decision-grade
flags (`api/v1/schemas/options.py:320-452`).

The service extracts contract snapshots with bid/ask, spread, Greeks, OI,
source, freshness, provider quality, and data quality from fixtures
(`src/services/options_lab_service.py:1464-1515`). Tests confirm synthetic
fixture decisions fail closed: `decisionLabel` is "data insufficient", no
preferred strategy is emitted, `decisionGrade=false`, gates are blocked/manual
review, and no external calls, order placement, broker connection, portfolio
mutation, or trading recommendation are allowed
(`tests/api/test_options_lab.py:1220-1254`).

### Product Gaps

- Live provider authority is not product-ready until options chains, bid/ask,
  OI, volume, IV, Greeks, expiration calendars, and corporate-action handling
  are validated against a real source contract.
- IV Rank and expected move can be useful only when source type, model version,
  and freshness are explicit.
- Spread and liquidity gates must remain blockers, not just warnings.
- UX should frame outputs as scenario readiness and risk structure, not "best
  contract" or trade recommendation.
- Portfolio-linked covered call or cash-secured put analysis should remain
  deferred until a read-only portfolio projection contract exists. Broker tokens,
  raw account payloads, order routing, and portfolio mutation remain forbidden.

### Options Readiness Contract

```text
optionsResearchReady: boolean
dataQualityTier: live_usable | delayed_usable | synthetic_demo_only | insufficient
decisionGrade: boolean
providerAuthority: official_or_authorized | observation_only | fixture | unavailable
liquidityGate: pass | manual_review | blocked
ivGreeksGate: pass | manual_review | blocked
spreadGate: pass | manual_review | blocked
scenarioCoverage: expiration_payoff | pre_expiration_model | unavailable
noTradingBoundary: true
```

## 6. Admin IA Audit: Operator L0 To L4

The frontend has many admin routes today: system settings, logs, evidence
workflow, notifications, market providers, provider circuits, users, user
activity, and cost observability (`apps/dsa-web/src/App.tsx:389-425`). Docs
already say Admin/Ops pages may be dense, but must start with state, impact,
recommended action, evidence, then details; raw logs and diagnostics need
explicit expansion (`docs/admin-ops/README.md:22-31`).

The next IA should group pages by operator decision level:

| Level | Purpose | Pages / panels | Collapsed panel contents |
| --- | --- | --- | --- |
| L0 Overview | "Is the research OS safe to trust right now?" | Admin/Ops home, release evidence, health/readiness summary | global readiness, failing surfaces, active blockers, last-known-good, no secrets |
| L1 Incidents and evidence | "What failed, when, and where is proof?" | Admin Logs, Evidence Workflow, market-provider drill-through | sanitized event timeline, request ids, affected surfaces, evidence refs, bounded error classes |
| L2 Data and provider ops | "Which data source or cache is stale/fallback/unavailable?" | Market Providers, Provider Circuits, Cost Observability, MarketCache panels | provider matrix, source tier, trust level, freshness, cache age, quota/cost, circuit state |
| L3 User and product support | "Which user/product object is affected?" | Admin Users, user activity, user analysis/scanner/backtest summaries | user-safe id, account status, product events, report/run summaries, redacted raw payload details |
| L4 Controlled action and raw detail | "What privileged action is allowed and audited?" | system settings, notifications, security actions, force-refresh/prewarm actions | reason-required action form, dry-run preview, audit trail, secrets never displayed, rollback notes |

This preserves dense operator power while reducing details sprawl:

- every admin page starts with L0/L1 state, impact, next action, and evidence;
- raw provider/schema/debug data is collapsed by default;
- logs and drill-through are cross-linked instead of duplicated inline;
- security, sessions, tokens, prompts, files, broker/account data, and secrets
  follow the redaction matrix in the Admin Data Control Center design
  (`docs/audits/admin-data-control-center-design.md:148-160`);
- provider operations stays read-only, aggregates existing metadata, and drills
  to Admin Logs without exposing credentials or changing provider behavior
  (`docs/design/wolfystock-market-provider-operations-dashboard.md:11-78`).

## 7. Phased Backlog And Next Goal Candidates

### P0: Data And Provenance Foundation

Goal candidate: `T-893-GOAL research-readiness contract skeleton`

Allowed final diff:

- `src/services/research_readiness_contract.py`
- `tests/services/test_research_readiness_contract.py`
- `docs/product/RESEARCH_OS_NEXT_ARCHITECTURE.md`
- optional docs changelog line

Forbidden:

- no provider order, provider runtime, cache TTL, LLM prompt, scoring, ranking,
  API response shape removal, frontend UI, auth, storage, broker, or CI changes.

Acceptance:

- pure projection helper maps existing `dataQualityReport`, source-confidence,
  trust/freshness metadata, and no-advice boundaries into `ResearchReadinessV1`;
- tests cover ready, observe-only, insufficient, blocked, and waiting states.

### P1: Research Score Contracts Across Home AI And Market Intelligence

Goal candidate: `T-894-GOAL home-market research-ready projection`

Allowed final diff:

- additive backend projection in Home AI/Market Overview response assembly;
- focused API/service tests;
- docs update.

Forbidden:

- no provider calls, no prompt/routing/model changes, no score threshold changes,
  no task status semantics change unless explicitly scoped, no frontend rewrite.

Acceptance:

- Home AI and Market Intelligence both expose the same `researchReadiness`
  object;
- result-bearing weak analyses can still complete technically, but the product
  verdict says `researchReady=false` with blocking reasons.

### P2: Top-Down Scanner Integration

Goal candidate: `T-895-GOAL scanner top-down context contract`

Allowed final diff:

- scanner run response additive `scannerContextFrame`;
- adapter/tests that consume existing Market Overview, Liquidity, Rotation, and
  source-readiness payloads;
- no UI redesign beyond consumer-safe labels if separately authorized.

Forbidden:

- no scanner ranking, sorting, thresholds, selection, provider runtime, cache, or
  notification changes.

Acceptance:

- Scanner can explain whether a shortlist came from a supportive, mixed,
  observe-only, or insufficient top-down environment;
- AI remains interpretation only and cannot imply buy/sell/order advice.

### P3: Options Readiness

Goal candidate: `T-896-GOAL options readiness authority gates`

Allowed final diff:

- options readiness projection, authority/gate tests, docs;
- live-provider adapter design only unless a separate provider Goal authorizes
  code.

Forbidden:

- no broker, no order routing, no portfolio mutation, no personalized advice,
  no hidden live provider probing, no provider credential logging.

Acceptance:

- Options Lab clearly distinguishes demo, delayed usable, live usable, and
  insufficient;
- spread/liquidity/IV/Greeks/OI gates can block decision-grade output.

### P4: Admin IA

Goal candidate: `T-897-GOAL admin ops IA consolidation blueprint`

Allowed final diff:

- docs/product or docs/audits IA contract;
- optional frontend route taxonomy doc;
- optional tests only if a later UI slice is scoped.

Forbidden:

- no admin mutations, auth/RBAC behavior changes, route deletion, raw payload
  expansion, provider behavior, or secrets exposure.

Acceptance:

- L0/L1/L2/L3/L4 admin groupings are documented with page ownership, default
  collapsed detail policy, drill-through targets, and safe labels.

## Implementation Guardrails

- Keep this work additive until a Goal explicitly scopes runtime behavior.
- Reuse existing provider capability, data-source route diagnostics,
  data-quality contracts, Market Overview trust fields, Options gates, and
  Scanner explainability vocabulary.
- Do not add buy/sell/order CTAs. Use research, observation, readiness,
  insufficient, and blocked language.
- Do not promote public proxy, stale, fallback, fixture, synthetic, or
  observation-only evidence to score-grade authority.
- Do not probe live providers in audit or tests unless a future provider Goal
  explicitly authorizes opt-in live checks with sanitized evidence.

## Completion Checklist For This Audit

- Main deliverable: `docs/codex/audits/archive/2026-06/T-892-research-os-product-gap-audit.md`
- Runtime code changed: no
- Frontend TSX/CSS changed: no
- Backend endpoint/service/provider/cache/storage/accounting/auth changed: no
- Provider probing performed: no
- Changelog updated: no, because this is an internal Codex audit document and
  the allowed optional changelog line is not needed for current users.
