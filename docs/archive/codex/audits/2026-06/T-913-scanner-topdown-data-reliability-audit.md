# T-913 Scanner Top-Down Data Reliability Audit

Task ID: T-913
Mode: READ-ONLY-AUDIT with explicit docs-only artifact and local commit authorization
Scope: implementation-ready product/data audit. No runtime code was changed.

## Executive Verdict

Scanner already has strong discovery primitives: market-specific profiles,
bounded universes, deterministic shortlist ranking, candidate diagnostics,
score caps, evidence packets, `scannerContextFrame`, and frontend fail-closed
readiness strips. The core reliability gap is that these pieces are not yet
assembled into a trustworthy top-down research workflow.

The current Scanner still behaves mostly as "run a market/profile screener and
inspect ranked candidates". It does not yet reliably answer:

```text
global regime/liquidity
-> asset class pressure
-> sector/theme/industry context
-> candidate evidence coverage
-> research-readiness boundary
```

For CN/A-share, the dominant problem is data-source availability and authority:
universe and realtime snapshot dependencies can block or force a degraded local
history path, while available CN public/proxy providers remain observation-only
and must not be promoted to score-grade evidence. For US, the dominant problem
is quality coverage: the profile can produce a shortlist from local history,
bounded seeds, optional quote/gap context, and technical/liquidity signals, but
it lacks explicit fundamentals, news/catalyst, earnings/event, sector/theme, and
per-candidate readiness coverage.

The safe next direction is additive projection and adaptation only. Do not alter
Scanner rank, score, filters, selection, provider order, cache behavior, or
runtime fallback semantics until a separate protected-domain task explicitly
authorizes it.

## Evidence Inventory

### Product And Contract Anchors

- T-892 defines the Research OS gap as missing first-class research readiness
  before score/action/shortlist interpretation, and requires projection-only
  `ResearchReadinessV1` before runtime semantics change
  (`docs/codex/audits/archive/2026-06/T-892-research-os-product-gap-audit.md:147`).
- T-892's desired Scanner workflow is global regime/liquidity -> asset classes
  -> sector/theme/style -> industries -> candidates -> evidence readiness
  (`docs/codex/audits/archive/2026-06/T-892-research-os-product-gap-audit.md:205`).
- The existing Scanner product contract already names `scannerContextFrame`
  fields and calls out missing `candidateReadiness`
  (`docs/codex/audits/archive/2026-06/T-892-research-os-product-gap-audit.md:249`).
- Scanner docs state the current market profiles are `cn_preopen_v1`,
  `us_preopen_v1`, and `hk_preopen_v1`, with shared run/history/review
  facilities but separated market semantics (`docs/market-scanner.md:33`).
- Scanner docs explicitly frame results as a pre-open observation list, not an
  automated execution instruction (`docs/market-scanner.md:193`).

### Backend, API, And Persistence

- `ScannerRunRequest` accepts `market`, `profile`, `shortlist_size`,
  `universe_limit`, `detail_limit`, `universe_type`, `theme_id`, and `symbols`
  (`api/v1/schemas/scanner.py:11`).
- `ScannerRunDetailResponse` exposes run metadata, diagnostics,
  `scannerContextFrame`, selected candidates, full candidate diagnostics, and
  shortlist rows (`api/v1/schemas/scanner.py:261`).
- Scanner endpoints include run creation, themes, history, strategy simulation,
  today/recent watchlists, status, and run detail
  (`api/v1/endpoints/scanner.py:134`, `api/v1/endpoints/scanner.py:220`,
  `api/v1/endpoints/scanner.py:251`, `api/v1/endpoints/scanner.py:288`,
  `api/v1/endpoints/scanner.py:345`, `api/v1/endpoints/scanner.py:371`).
- `MarketScannerService.run_scan()` dispatches to US/HK quote-market paths or
  the CN-specific universe/snapshot flow (`src/services/market_scanner_service.py:765`).
- Completed runs persist final diagnostics and generate `scannerContextFrame`
  for fresh responses (`src/services/market_scanner_service.py:1773`) and
  persisted detail responses (`src/services/market_scanner_service.py:4377`).
- Candidate public payloads retain rank, score, raw/final score, reasons,
  metrics, risk notes, diagnostics, and consumer diagnostics
  (`api/v1/schemas/scanner.py:204`).
- Schema gap: `scannerContextFrame` is currently an additive `Dict[str, Any]`
  field and candidates do not expose a typed `candidateReadiness` contract.
  That keeps legacy compatibility, but future implementation should add
  projection helpers and tests before depending on stronger typed semantics.

### Profiles, Shortlist, Ranking, And Diagnostics

- Profiles define separate CN/US/HK thresholds, history depth, universe limits,
  and benchmark codes (`src/core/scanner_profile.py:39`,
  `src/core/scanner_profile.py:60`, `src/core/scanner_profile.py:84`).
- Shortlist selection is deterministic by final `score` descending and symbol
  tie-break, then AI interpretation is attached as a secondary layer
  (`src/services/market_scanner_service.py:1114`).
- CN scoring uses pre-rank, trend, momentum, breakout, liquidity, activity,
  volatility quality, relative strength, sector bonus, and penalties
  (`src/services/market_scanner_service.py:6126`).
- US scoring uses local history/quote-derived pre-rank, trend, momentum,
  liquidity, activity, volatility quality, relative strength, benchmark-relative
  behavior, gap context, and penalties (`src/services/market_scanner_service.py:6203`).
- Score caps and explainability mark missing, fallback, stale, partial, proxy,
  or unavailable evidence and set `scoreContributionAllowed=false` when
  authority is not score-grade (`src/services/market_scanner_service.py:6536`).
- Run diagnostics include coverage summary, provider diagnostics, scanner data,
  universe selection, history stats, quote stats, and candidate diagnostics
  depending on market (`src/services/market_scanner_service.py:995`,
  `src/services/market_scanner_service.py:2030`).
- Provider diagnostics are run-level attribution, not complete symbol-level
  provider trace (`docs/market-scanner.md:291`).

### scannerContextFrame And Readiness

- `_resolve_scanner_context_inputs()` can read market context, liquidity context,
  rotation context, `marketRegimeSynthesis`, `capitalFlowSignal`, and
  `rotationFamilyRollup` from diagnostics if those payloads are present
  (`src/services/market_scanner_service.py:3143`).
- `_build_scanner_context_readiness()` adapts macro and liquidity evidence into
  `build_research_readiness_v1()` with `noAdviceBoundary=true`
  (`src/services/market_scanner_service.py:3219`).
- The context frame emits `marketReadiness`, `macroRegime`, `liquidityFrame`,
  `assetClassBias`, `themeFrame`, `universePolicy`, and `noAdviceBoundary`
  (`src/services/market_scanner_service.py:3569`).
- `ResearchReadinessV1` fail-closes missing metadata and includes source
  authority, freshness, missing evidence, next evidence, and no-advice boundary
  fields (`src/services/research_readiness_contract.py:202`).
- Frontend `inferScannerResearchReadiness()` returns explicit
  `marketReadiness` when present, otherwise falls back to waiting,
  insufficient, or observe-only states (`apps/dsa-web/src/api/researchReadiness.ts:602`).
- Frontend `buildScannerTopDownContextView()` renders market, macro, liquidity,
  asset, theme, universe, and research-only chips without touching candidate
  rank/score order (`apps/dsa-web/src/api/researchReadiness.ts:639`).
- The Scanner page renders the readiness strip and top-down context strip above
  the dense status strip and table (`apps/dsa-web/src/pages/UserScannerPage.tsx:2777`).

### Tests And Public Safety

- Legacy Scanner detail responses remain accepted when `scannerContextFrame` is
  absent or empty (`tests/api/test_scanner.py:16`).
- Service tests cover supportive context, missing-context fail-close,
  fallback/proxy observe-only posture, and unavailable CN context blocking
  (`tests/test_market_scanner_service.py:927`,
  `tests/test_market_scanner_service.py:999`,
  `tests/test_market_scanner_service.py:1018`,
  `tests/test_market_scanner_service.py:1077`).
- Frontend tests verify the top-down context strip does not mutate ranking or
  score order, and missing context fails closed instead of becoming supportive
  (`apps/dsa-web/src/pages/__tests__/UserScannerPage.test.tsx:1046`,
  `apps/dsa-web/src/pages/__tests__/UserScannerPage.test.tsx:1076`).
- Public safety tests assert degraded CN market data is disclosed without
  guaranteed-confidence language or direct trading instructions
  (`tests/test_market_scanner_public_safety.py:121`).

## CN/A-Share Failure Modes

### 1. Universe Dependency Can Block The Run

CN Scanner first tries local universe cache, then Tushare stock list, then local
DB/internal fallback, then AkShare stock list. If all fail, it returns
`universe_source_unavailable` with compact attempt diagnostics
(`src/services/market_scanner_service.py:4934`). The product doc mirrors this
order and notes `Tushare stock_basic` is no longer a hard prerequisite, but a
configured/usable universe is still required (`docs/market-scanner.md:75`).

Current user impact:

- Missing `SCANNER_LOCAL_UNIVERSE_PATH` cache is recoverable only if another
  source or local fallback has enough symbols.
- Tushare permission/config problems remain visible as bounded reason codes,
  not as usable score evidence.
- Builtin and DB fallback can make the run proceed, but they are not equivalent
  to fresh, complete A-share market coverage.

### 2. Realtime Snapshot Can Block Or Degrade The Run

After universe resolution, CN Scanner needs a market snapshot from AkShare or
Efinance. If both fail, it attempts `local_history_degraded`; if local history
is insufficient, the scan fails with `no_realtime_snapshot_available`
(`src/services/market_scanner_service.py:5221`). The docs list the same
snapshot fallback chain and common reason codes (`docs/market-scanner.md:600`).

Current user impact:

- "CN scanning is unusable" is consistent with a missing/invalid universe plus
  failed AkShare/Efinance snapshot and insufficient local history.
- `local_history_degraded` can keep a run alive, but it relaxes turnover handling
  and marks the result as a lower-confidence pre-open reference, not a full
  realtime scan (`src/services/market_scanner_service.py:5302`).

### 3. Source Authority Is Observation-First

AkShare is scanner-allowed only for top-N observation/enrichment, has delayed
freshness, and is explicitly not official decision-grade live data
(`src/services/provider_capability_matrix.py:250`). Efinance is public proxy
observation, rejected for official quotes and score inputs
(`src/services/provider_capability_matrix.py:1578`). Tushare Pro is gated,
plan-dependent, key-required, and rejected for score inputs or provider-order
changes (`src/services/provider_capability_matrix.py:1886`). pytdx is a
usable-with-caution baseline but rejected for official quotes and score inputs
(`src/services/provider_capability_matrix.py:1826`).

Current user impact:

- Even a "healthy" public CN provider must remain observation-only unless a
  separate source-authority task approves score-grade use.
- CN provider health and data-readiness diagnostics must not expose quotes,
  universes, raw provider payloads, or scoring output
  (`docs/market-overview/market-intelligence-smoke-checklist.md:111`).

### 4. Current Context Adapter Is Present But Not Fed By Normal CN Runs

`scannerContextFrame` can consume `market_temperature`, `liquidity_context`, and
`rotation_context` from diagnostics, but the normal CN run diagnostics built in
`run_scan()` contain scanner-local universe/snapshot/history diagnostics, not a
complete Market Overview/Liquidity/Rotation context bundle
(`src/services/market_scanner_service.py:1022`,
`src/services/market_scanner_service.py:3143`).

Current user impact:

- The frontend can display blocked/insufficient CN context safely, but the
  backend does not yet provide a complete top-down CN context frame for standard
  scanner runs.
- CN failures are currently easier to diagnose in the secondary diagnostics
  area than in the primary research workflow.

### 5. API/Frontend Limitation Is Presentation, Not Root Cause

The frontend already has a safe fail-closed path for missing
`scannerContextFrame` and can render blocked/observe-only labels. The current
CN usability gap is therefore not a TSX rendering blocker. It is that the
backend run payload does not yet project CN universe/snapshot/provider failure
diagnostics into the primary readiness field, and the API has no per-candidate
readiness contract to explain whether a selected A-share is supported by fresh,
complete, score-grade evidence.

Current user impact:

- A failed or degraded CN run can be technically diagnosable while still feeling
  unusable because the top Scanner workflow does not lead with the blocking
  reason.
- Adding more frontend copy alone would hide the real data-source and authority
  problem; the next slice should adapt existing backend diagnostics into
  readiness first.

## US Scanner Quality Limits

### 1. Universe Coverage Is Bounded, Not Full-Market

US Scanner resolves universe from `LOCAL_US_PARQUET_DIR` /
`US_STOCK_PARQUET_DIR`, then local `stock_daily`, then a curated liquid seed
supplement when local coverage is thin (`src/services/market_scanner_service.py:2472`).
Docs explicitly state the current default is not a full-market blind scan
(`docs/market-scanner.md:343`).

Quality limit:

- A shortlist can be "clean" but still miss relevant stocks when parquet/local
  history coverage is incomplete or seed-only.
- `coverage_strategy`, `local_symbol_count`, and `supplemented_seed_count`
  explain narrow coverage, but they are not yet part of a front-and-center
  research readiness gate.

### 2. Ranking Inputs Are Mostly Technical/Liquidity

US pre-rank and final score emphasize local OHLCV-derived liquidity, trend,
momentum, volatility/tradability, benchmark-relative behavior, and optional
gap/quote context (`src/services/market_scanner_service.py:2856`,
`src/services/market_scanner_service.py:6203`). Candidate construction falls
back to historical close and prior daily features when live quote is missing
(`src/services/market_scanner_service.py:2926`,
`src/services/market_scanner_service.py:2973`).

Quality limit:

- No first-class per-candidate fundamentals, valuation, filings, earnings, news,
  catalyst, or event evidence is included in the shortlist ranking contract.
- Sector/theme/industry context does not currently influence US ranking through
  an audited mapping.
- Gap context is optional; missing live quote only adds a small penalty and
  should be surfaced as readiness/evidence coverage, not inferred accuracy.
- The API lacks a typed per-candidate readiness/evidence object that says
  "technical-only", "missing catalyst/news", "fallback quote", or
  "history-only" in a controlled product vocabulary.

### 3. Provider Policy Prevents Broad External Enrichment

Alpaca is suitable for configured US quote/OHLCV enrichment but not broad
research (`src/services/provider_capability_matrix.py:273`). FMP is explicitly
not scanner-allowed despite being useful for fundamentals/statements; its
operator note says not to run scanner-wide (`src/services/provider_capability_matrix.py:311`).
Finnhub is bounded only and not recommended for scanner fanout
(`src/services/provider_capability_matrix.py:351`). GNews and Tavily are not
scanner-wide providers (`src/services/provider_capability_matrix.py:389`,
`src/services/provider_capability_matrix.py:408`).

Quality limit:

- The correct fix is not to turn on broad provider fanout. It is to project what
  evidence exists, enrich only top-N/cached/manual-review candidates when a
  later task scopes it, and keep provider quota/authority boundaries visible.

### 4. AI Interpretation Is Not A US Quality Fix

Scanner AI is a secondary explanation layer, cannot change deterministic
rank/score, and currently skips non-CN profiles (`src/services/scanner_ai_service.py:21`,
`src/services/scanner_ai_service.py:111`). The docs also state AI does not
replace rank/score, does not become first-round selection, and does not block
Scanner (`docs/market-scanner.md:215`).

Quality limit:

- US accuracy must improve through evidence coverage and top-down context, not
  through ungrounded AI narration.

## Desired Top-Down Workflow Map

| Workflow layer | Existing source | Current status | Missing for Scanner |
| --- | --- | --- | --- |
| Global regime | Market Overview / Market Temperature `marketRegimeSynthesis` | Context reader exists if diagnostics include it | Adapter to inject existing context into Scanner runs without provider/runtime changes |
| Liquidity / asset pressure | Liquidity Monitor `capitalFlowSignal`, `liquidityImpulseSynthesis` | Observation-only semantics already documented | Scanner-specific bridge that preserves `observationOnly`, `sourceAuthorityAllowed=false`, `scoreContributionAllowed=false` |
| Asset class frame | Market Overview + Liquidity across equities, rates, USD, gold, crypto | `assetClassBias` projection exists | Explicit data adapter and copy that says research context, not trade direction |
| Theme / sector | Rotation Radar `rotationFamilyRollup`, `themeFlowSignal`; sector taxonomy | Context reader exists if diagnostics include it | Map rotation themes to Scanner universe/theme labels; keep proxy/static/taxonomy-only out of ranking authority |
| Industry | Scanner boards for CN; taxonomy/theme metadata | CN has board context; US/HK mostly lacks industry evidence | Add additive industry/theme coverage labels per candidate without score changes |
| Candidate stocks | Scanner shortlist/candidates/evidence packets | Strong existing rows and diagnostics | Per-candidate `ResearchReadinessV1` or evidence coverage strip |
| Evidence readiness | `ResearchReadinessV1`, source confidence, scanner evidence packet | Run-level readiness exists; candidate-level readiness missing | Candidate readiness adapter; no rank/score mutation |
| Safety boundary | no-advice / no-execution copy and tests | Existing strips and tests | Preserve wording and sentinel tests through all future slices |

## How Scanner Should Consume Existing Surfaces

1. Market Overview should provide cached/assembled `marketRegimeSynthesis`,
   Market Temperature trust fields, and briefing/indicator freshness into a
   Scanner context adapter. Scanner must read this as context evidence only.
2. Liquidity Monitor should feed `capitalFlowSignal`,
   `liquidityImpulseSynthesis`, and coverage diagnostics. These remain
   observation-only unless an explicit future source-authority task changes the
   underlying liquidity policy (`docs/liquidity/README.md:25`).
3. Rotation Radar should feed `rotationFamilyRollup` and `themeFlowSignal`.
   Fallback/static/taxonomy-only themes remain visible observation lanes, not
   headline/ranking authority (`docs/rotation/README.md:17`).
4. `scannerContextFrame` should continue using
   `build_research_readiness_v1()` and existing fields. Do not create a parallel
   readiness verdict.
5. Candidate evidence should derive from existing `score_explainability`,
   `source_confidence`, `evidence_packet`, and diagnostics. Do not call
   providers to beautify missing rows.
6. Frontend should keep compact strips and candidate-first workflow. Diagnostics
   remain secondary and collapsed by default.

## Safe Phased Execution Plan

### T-914 CN Scanner Blocked-State / Readiness Projection

Goal: make CN/A-share blocked/degraded states legible at the top of Scanner
without changing provider runtime or ranking.

Suggested allowed scope:

- Backend tests around CN failure/degraded diagnostics.
- Additive projection code that adapts existing CN universe/snapshot diagnostics
  into `scannerContextFrame.marketReadiness` and bounded CN blocker labels.
- Frontend tests only if needed to assert blocked/insufficient copy from existing
  payload.

Must not change:

- AkShare/Efinance/Tushare/pytdx provider order, live calls, fallback policy,
  source authority, score caps, ranking, filters, or cache semantics.

Acceptance evidence:

- CN missing universe -> visible blocked/insufficient readiness.
- CN snapshot failure + no degraded local history -> visible blocked readiness.
- CN local history degraded -> observe-only/fallback readiness.
- No raw provider payload, credential, stack trace, or internal route leakage.

### T-915 Scanner Top-Down Context Data Adapter

Goal: attach existing Market Overview, Liquidity Monitor, and Rotation Radar
context into Scanner diagnostics/`scannerContextFrame` additively.

Suggested allowed scope:

- A pure adapter/helper that maps existing cached/service outputs into the
  `scannerContextFrame` input vocabulary.
- Service tests proving the adapter is projection-only and does not change
  candidate rank, score, order, filters, provider calls, or cache writes.

Must not change:

- Scanner ranking/scoring/filtering.
- Market Overview/Liquidity/Rotation scoring, provider, cache, or source
  authority semantics.
- API contract beyond already-additive fields unless explicitly authorized.

Acceptance evidence:

- Missing external context fails closed.
- Proxy/fallback/stale context remains observe-only.
- Supportive context can render as supportive only when source authority and
  score contribution are explicitly allowed by existing payloads.

### T-916 Scanner Evidence Coverage Per Candidate

Goal: expose per-candidate evidence readiness/coverage from existing candidate
diagnostics.

Suggested allowed scope:

- Additive candidate readiness helper based on `score_explainability`,
  `source_confidence`, `evidence_packet`, and existing candidate diagnostics.
- Tests for complete, fallback, stale, partial, missing quote, missing history,
  and data-failed candidates.
- Optional compact frontend strip/chips in candidate detail only.

Must not change:

- Candidate score, `raw_score`, `final_score`, rank, shortlist membership, or
  selection order.
- Provider calls or enrichment fanout.

Acceptance evidence:

- Candidate with fallback/history-only quote stays observe-only.
- Candidate with missing fundamentals/news/catalyst shows missing evidence
  without implying trade readiness.
- Data-failed rows remain data-failed and do not get fabricated fields.

### T-917 Scanner Ranking Audit / Guardrails

Goal: document and test what ranking currently uses, where it is weak, and what
would require separate protected-domain approval.

Suggested allowed scope:

- Tests that freeze current score components and order for representative CN/US
  fixtures.
- Audit doc or comments explaining current technical/liquidity-heavy ranking
  assumptions and gaps.
- Guard tests ensuring context/readiness adapters cannot mutate rank/score.

Must not change without separate approval:

- Score component weights.
- Ranking tie-breaks.
- Thresholds, filters, universe construction, or candidate selection.

Acceptance evidence:

- Golden CN/US candidate orders remain stable.
- Readiness/context payload changes cannot reorder rows.
- Any proposed score changes are deferred into a separate task with explicit
  protected-domain authorization.

### T-918 Frontend Top-Down Workflow Refinement

Goal: make Scanner read as a top-down research workflow while preserving compact
candidate-first ergonomics.

Suggested allowed scope:

- Compact top-down strip refinements and candidate detail evidence coverage.
- Browser/test proof for CN blocked, US mixed/observe-only, missing context, and
  supportive context states.
- Public safety assertions against buy/sell/order/trading-copy leakage.

Must not change:

- Data fetching behavior beyond consuming already-present fields.
- Candidate sorting, selection, row actions, export contract, backtest handoff,
  or AI theme flow.

Acceptance evidence:

- First viewport shows readiness/top-down state before over-reading candidate
  score.
- Candidate table remains primary; diagnostics stay collapsed by default.
- No card sprawl or raw provider/schema/debug leakage.

## Protected / High-Risk Domains Requiring Separate Approval

The following must stay out of T-914 through T-918 unless the future prompt
explicitly authorizes them:

- Scanner scoring, ranking, selection, thresholds, sorting, filters, and
  shortlist membership.
- Provider runtime order, live-call paths, retries, timeouts, fallback behavior,
  provider activation, source-authority promotion, or freshness/live labeling.
- MarketCache TTL/SWR/cold-start/background refresh/cache-key semantics.
- Market Overview, Liquidity Monitor, Rotation Radar score/stage/headline
  eligibility, rank eligibility, or source authority semantics.
- API response shape changes beyond existing additive fields, stored contract
  version changes, database migrations, or storage schema changes.
- Config, credentials, `.env` semantics, dependency/lockfile/CI changes.
- AI/LLM prompts, routing, model order, retry/fallback thresholds, or generated
  recommendation semantics.
- Auth/RBAC/security, broker/order, portfolio/accounting, backtest calculation,
  notification routing, or execution workflows.

## Implementation-Ready Recommendation

Proceed in this order:

1. T-914: make CN blocked/degraded readiness visible and fail-closed using
   existing diagnostics.
2. T-915: add the top-down context data adapter that feeds
   `scannerContextFrame` from existing Market Overview, Liquidity, and Rotation
   payloads.
3. T-916: add per-candidate evidence coverage/readiness from existing
   diagnostics and evidence packets.
4. T-917: freeze ranking assumptions and define separate approval requirements
   for any score/rank changes.
5. T-918: refine the frontend workflow once the backend projections are stable.

This sequence keeps Scanner trustworthy without prematurely widening provider
runtime, cache, ranking, or source-authority semantics.
