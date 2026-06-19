# T-1758 Market Data P0 Root-cause Map

Status: READY

This report is a static, read-only diagnosis of why WolfyStock market data is not delivering useful consumer evidence across the P0 surfaces called out by T-1757. It does not make runtime, provider, API, frontend, cache, database, broker, pricing, or credential changes.

T-1757's detailed audit artifact was not present in this worktree. The issue IDs and symptoms below are therefore mapped from the user-provided T-1757 summary plus the current code, docs, and tests.

## Protected-domain Boundary

Hard stop for implementation:

- Provider runtime calls, provider auth setup, provider feed entitlement checks, provider quota checks, and live provider probes are outside this task.
- Cache mutation, cache accounting changes, parquet/DB writes, scanner runs, broker sync, pricing engine changes, and production-like credential validation are outside this task.
- Local GET validation was not used here because several market endpoints can refresh provider/cache state through `MarketCache.get_or_refresh`; this report recommends safe commands but does not execute runtime calls.
- Provider response bodies, private URLs, and sensitive identifiers are intentionally not copied into this report.

## Executive Diagnosis

The endpoints are mostly wired correctly. The broad failure mode is not "frontend points at missing routes"; it is that consumer-facing evidence gates are correctly rejecting fallback, stale, proxy-only, taxonomy-only, unavailable, or insufficient-coverage inputs.

Shared root causes:

- Market Overview panels default through cache/fallback wrappers; if provider-backed or official rows are absent, stale, or incomplete, `sourceAuthorityAllowed` and `scoreContributionAllowed` are disabled before consumer pages see the data.
- Decision Cockpit is downstream of Market Regime Decision and Research/Options context. Its engine blocks proxy/fallback/observation-only drivers, has intentional unavailable drivers, and caps confidence when scoring driver count is too low.
- Liquidity Monitor reads cached market surfaces by default and does not make external provider calls. Most indicator families require authorized real sources or are intentionally observation-only, so the score and regime are unavailable when fewer than three reliable indicators survive.
- Rotation Radar can show observation or taxonomy content, but headline ranking is quarantined unless provider authority, constituent coverage, freshness, and theme-flow gates pass. Static/taxonomy/fallback themes are visible but excluded from "strongest" and "accelerating".
- Research Radar is not a live market-data provider surface. Its API is read-only and depends on a user-scoped completed scanner run and/or watchlist overlay; no such source means no research evidence.
- The Home market briefing uses Market Overview trust inputs; the separate homepage intelligence endpoint is a fixture/metadata bundle, not a live market evidence feed.

## Endpoint Inventory

| Surface | Consumer route/page impact | Backend endpoint | Data source/provider chain | Current fallback behavior | Suspected root cause | Confidence | Protected-domain risk | Recommended implementation task | Recommended validation command | Parallelization |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Market Overview: indices | Market Overview panels and downstream Market Temperature | `GET /api/v1/market-overview/indices` via `MarketOverviewService.get_indices()` | Quote panel, yfinance-backed quote items, cache wrapper | Uses memory/persistent snapshot or static fallback when fetcher data is unusable | Provider/cache availability and freshness gates reject fallback/stale/no-value rows; route is wired | High | Provider/cache if fixed with live refresh | Add a read-only panel readiness summary that reports reliable row count and rejection buckets before provider work | `python -m pytest tests/api/test_market_intelligence_payload_smoke.py -k market_overview -q` | Parallel with docs/diagnostics; provider fix is serial/manual |
| Market Overview: volatility | Market Overview volatility and regime inputs | `GET /api/v1/market-overview/volatility` | VIX official overlay when present, otherwise quote-derived panel rows | yfinance proxy rows are delayed/capped; fallback rows are excluded from scoring | Official VIX source/cache may be absent; proxy-only VIX is intentionally not score-grade | High | Provider/cache/auth boundary for official rows | Define official VIX readiness check and make UI diagnostics expose why VIX is capped | `python -m pytest tests/test_market_intelligence_smoke_checklist.py -k VIX -q` | Parallel for diagnostics; official source work serial |
| Market Overview: sentiment | Market Overview sentiment | `GET /api/v1/market-overview/sentiment` | Market sentiment snapshot from configured sentiment sources with bounded fallback | Throws into fallback if insufficient history or provider failure | Sentiment history/provider coverage is insufficient for reliable live evidence | Medium | Provider runtime if live source must be validated | Add provider-free diagnostics for sentiment history sufficiency and source age | `python -m pytest tests/api/test_market_intelligence_payload_smoke.py -k sentiment -q` | Parallelizable |
| Market Overview: funds flow | Market Overview funds-flow panel, liquidity context | `GET /api/v1/market-overview/funds-flow` | Quote-derived ETF proxies such as broad index ETFs | Explicitly `observationOnly`, source authority false, score contribution false | This is intentionally a proxy surface, not a real fund-flow source; product expects evidence this route cannot provide | High | Real flow provider/auth/cache boundary | Split UI copy and diagnostics between "proxy observation" and "real flow unavailable"; plan real flow source separately | `python -m pytest tests/api/test_market_intelligence_payload_smoke.py -k funds_flow -q` | UI/diagnostics parallel; real provider serial/manual |
| Market Overview: macro | Market Overview macro, Market Temperature, Decision Cockpit | `GET /api/v1/market-overview/macro` | Official macro point cache plus yfinance quote rows | Official overlays can be missing; quote rows are delayed/capped | Official macro coverage/freshness is not consistently score-grade, leaving macro evidence degraded | High | Official macro provider/cache boundary | Build an implementation checklist for each required official series and readiness reason | `python -m pytest tests/api/test_market_intelligence_payload_smoke.py -k macro -q` | Diagnostics parallel; provider/cache serial |
| Market Temperature and Regime Decision | Market Overview summary, Home briefing, Decision Cockpit | `GET /api/v1/market/temperature`; `GET /api/v1/market/regime-decision` | Market Overview snapshot plus Liquidity Monitor and Rotation Radar rollups | If reliable inputs are insufficient, emits unavailable/degraded frames and fallback narrative | Upstream market, liquidity, and rotation evidence cannot pass score-grade gates often enough | High | Provider/cache plus scoring-policy review | Treat as downstream; do not tune confidence until upstream evidence counts are improved and measured | `python -m pytest tests/api/test_market_intelligence_payload_smoke.py -k temperature -q` | Must follow upstream work |
| Decision Cockpit | `/market/decision-cockpit` low-confidence regime | `GET /api/v1/market/decision-cockpit` | `MarketOverviewService.get_decision_cockpit()` and pure regime engine outputs | Blocks proxy/fallback/observation-only drivers; reports missing/blocked evidence | Data availability plus strict driver gating. Dealer gamma is intentionally unavailable in v1; research/options context can also be absent | High | Provider/auth for upstream data; product-policy review for confidence caps | After upstream fixes, run a driver-by-driver cockpit readiness audit before changing thresholds | `python -m pytest tests/api/test_market_decision_cockpit.py -q` if present, otherwise `python -m pytest tests/api -k decision_cockpit -q` | Serial after upstream evidence; threshold review manual |
| Liquidity Monitor | `/market/liquidity-monitor`; T-1757 WS-029 | `GET /api/v1/market/liquidity-monitor` | Cache-only reads from crypto, volatility, rates, macro, FX/commodities, funds-flow, breadth, CN/HK, futures panels | No external provider calls by default; regime unavailable when reliable indicator count is under threshold or confidence is too low | Coverage/provider activation issue, not route wiring. Current static code exposes 12 indicator families and 39 named required inputs; T-1757's "1 of 49" denominator was not found in current code and needs live-response reconciliation | High for root class; Medium for exact denominator | Provider auth, cache freshness, paid/official data, possible source-review boundary | First add a read-only coverage matrix that compares required, fulfilled, missing, and score-eligible inputs per family; then activate real sources by family | `python -m pytest tests/api/test_market_intelligence_payload_smoke.py -k liquidity -q` | Coverage report parallel; provider activation serial/manual |
| Rotation Radar: US | `/market/rotation-radar`; T-1757 WS-031 | `GET /api/v1/market/rotation-radar?market=US` | Configured quote provider first, yfinance fallback for missing quotes, shared market cache when enabled | Static/fallback/taxonomy/synthetic/unavailable themes are visible but excluded from headline ranking | Provider configuration/feed coverage may be missing, and ranking quarantine intentionally blocks non-authoritative themes. Tests show even authority-spine scenarios can remain observation-only if theme authority is not proven | High | Provider auth/feed entitlement, provider budget, ranking-policy review | Validate configured quote provider coverage and separately review ranking authority gates before altering theme rankings | `python -m pytest tests/api/test_market_rotation_radar.py -k "fallback or authority" -q` | Provider validation serial/manual; tests parallel |
| Rotation Radar: non-US | Rotation Radar non-US taxonomy lanes | `GET /api/v1/market/rotation-radar?market=CN/HK/...` | Static taxonomy projection | Taxonomy-only themes, no headline strongest/accelerating themes | Non-US route is currently taxonomy-only by design; no real theme ranking source exists | High | Provider/data-contract boundary | Decide product contract: show taxonomy-only explicitly or add real market-specific theme providers | `python -m pytest tests/api/test_market_rotation_radar.py -k taxonomy -q` | Contract review serial; UI copy parallel |
| Home market briefing | Guest Home market briefing | `GET /api/v1/market/market-briefing` called by Home dashboard | Market Overview trust snapshot plus downstream liquidity/rotation context | Returns conservative unavailable/degraded briefing when conclusion gates fail | Same upstream data-quality gates as Market Temperature; Home is not independently failing | High | Upstream provider/cache boundary | Keep Home downstream; validate after Market Overview/Liquidity/Rotation evidence readiness improves | `python -m pytest tests/api/test_market_intelligence_payload_smoke.py -k briefing -q` | Must follow upstream |
| Homepage intelligence bundle | Home intelligence widgets | `GET /api/v1/homepage/intelligence` | `HomepageIntelligenceService` fixture/manifest bundle | Static sample freshness and bounded metadata | If product expects live market evidence from this endpoint, the issue is a data-contract mismatch; endpoint is intentionally runtime-decoupled | High | None for diagnosis; contract change if re-scoped | Document whether this endpoint remains fixture-only or gets a separate live evidence contract | `python -m pytest tests/api -k homepage_intelligence -q` | Parallelizable contract/doc task |
| Research Radar and queue | `/research/radar`; `/research/queue`; T-1757 evidence gaps | `GET /api/v1/research/radar`; `GET /api/v1/research/queue` | User-scoped completed scanner run, scanner candidate evidence, watchlist overlay; queue can accept market input internally but endpoint does not pass market input | Empty/fail-closed when no completed scanner payload or watchlist context exists | Not a market provider failure. It is a prerequisite-data and route contract issue: the public endpoint is scanner/watchlist-driven and read-only | High | Database/scanner runtime if generating evidence; API contract if injecting market context | Add explicit readiness diagnostics for scanner/watchlist prerequisites; decide whether market context should feed `/research/queue` | `python -m pytest tests/api -k research_radar -q` | Diagnostics parallel; scanner/DB changes serial/manual |
| Data readiness diagnostics | Operator-facing preflight | `GET /api/v1/market/data-readiness` | Local file/import/config inspection only | Does not call providers or mutate runtime | Safe diagnostic route exists, but it covers only a subset of consumer evidence readiness | High | Low if kept local-only | Extend readiness output with consumer-surface evidence gates without provider calls | `curl -sS "$API_BASE/api/v1/market/data-readiness?symbols=AAPL,MSFT,SPY"` when local server is already running | Parallelizable |

## Route and Page Impact

Market Overview:

- Frontend calls `marketOverviewApi.getIndices`, `getVolatility`, `getSentiment`, `getFundsFlow`, and `getMacro`.
- Backend routes are registered under `/api/v1/market-overview/*`.
- The service marks items with freshness, fallback state, source authority, score eligibility, and rejection reasons before UI display.
- Impact: consumer panels can render, but useful evidence is often disabled because fallback/proxy/stale rows are not allowed to drive score-grade conclusions.

Decision Cockpit:

- Frontend calls `/api/v1/market/decision-cockpit`.
- Backend composes regime decision, research preview, options observation, action framework, and risk framing.
- Impact: cockpit regime confidence is low when market-regime drivers are blocked or missing. This is expected until macro, liquidity, breadth, rotation, and research evidence become score-grade.

Liquidity Monitor:

- Frontend calls `/api/v1/market/liquidity-monitor`.
- Backend builds 12 indicator families from cached panels and provider activation policies.
- Impact: many indicators are visible only as missing or observation-only. If fewer than three reliable indicators survive, regime is unavailable and score defaults to neutral.

Rotation Radar:

- Frontend calls `/api/v1/market/rotation-radar?market=...`.
- Backend can return headline, observation, and taxonomy lanes.
- Impact: real headline theme ranking is empty when provider trust, coverage, or theme-flow authority is missing. Taxonomy and fallback content are kept out of strongest/accelerating lists by policy.

Home market briefing:

- Guest home calls `/api/v1/market/market-briefing`.
- It inherits Market Temperature quality gates.
- The separate `/api/v1/homepage/intelligence` endpoint is a static intelligence bundle and should not be counted as live market evidence.

Research Radar:

- Frontend calls `/api/v1/research/radar` and `/api/v1/research/queue`.
- Both endpoints are authenticated, read-only projections from existing scanner/watchlist evidence.
- Impact: evidence gaps are expected when no completed user-scoped scanner run or watchlist overlay exists. This surface is not currently wired to live market provider evidence.

## Data Source and Provider Chain

Market Overview provider chain:

1. Fetcher attempts provider-backed or official/cache-backed panel data.
2. `_cached_payload` rejects fallback-only or no-usable-data responses.
3. It can return memory snapshot, persistent snapshot, or static fallback.
4. `_with_market_meta` classifies freshness, fallback state, source type, authority, and score eligibility.
5. Consumer evidence frames treat fallback/stale/cached/delayed/partial/unavailable states as degraded or blocked depending on the route.

Liquidity provider chain:

1. `LiquidityMonitorService` defaults to `allow_external_provider_calls=False`.
2. It reads already-available panels for crypto, volatility, rates, macro, FX/commodities, funds-flow, breadth, CN/HK, and futures context.
3. Provider activation policy decides whether each family has real-source authority.
4. Coverage diagnostics list required, fulfilled, missing, provider availability, proxy-only state, and score eligibility.
5. Aggregate regime is unavailable below the reliable indicator threshold.

Rotation provider chain:

1. The quote provider uses configured provider access first, then yfinance fallback for missing symbols.
2. Shared market cache can provide quote context.
3. Theme analysis builds headline, observation, and taxonomy lanes.
4. Ranking quarantine excludes static, fallback, taxonomy-only, synthetic, unavailable, or insufficient-coverage themes from headline ranking.
5. Consumer snapshots hide provider internals and expose only consumer-safe availability and evidence state.

Research provider chain:

1. API reads the latest completed scanner payload for the authenticated user.
2. Radar service projects scanner candidates into research-only observations.
3. Queue aggregator combines scanner, watchlist, optional market input, and manual gaps.
4. Current endpoint passes scanner/watchlist input only, so market queue items are not generated there.

## Current Fallback Behavior

- Market Overview panels fall back to in-memory snapshot, persistent snapshot, or static fixtures when primary fetches are unusable.
- Funds-flow is intentionally quote-derived proxy evidence and is excluded from source-authoritative scoring.
- Market Temperature and Market Briefing produce conservative unavailable/degraded copy when the trust snapshot fails.
- Decision Cockpit reports blocked/missing drivers instead of manufacturing confidence.
- Liquidity Monitor uses cache-only inputs by default and disables regime conclusions when reliable coverage is too low.
- Rotation Radar shows observation/taxonomy content but excludes it from headline ranking.
- Research Radar fails closed when prerequisite scanner/watchlist evidence is absent.

## P0 Issue Root-cause Map

### WS-001: Consumer Pages Show No Evidence, Unavailable, or Degraded Data

Likely root cause: upstream market evidence cannot pass source authority, freshness, and score eligibility gates. This is a provider/cache/coverage issue with intentional consumer-safety filtering, not a general route-wiring failure.

Evidence:

- Market Overview panels use `_cached_payload` and `_with_market_meta` to reject fallback-only or unusable data and annotate fallback/stale/proxy states.
- Evidence framing treats degraded freshness and missing score-grade domains as blocked/observe-only.
- Market Temperature and Market Briefing inherit the same trust snapshot.
- Funds-flow is intentionally proxy-only and cannot provide authoritative evidence.

Confidence: High.

Next diagnostic: build a read-only evidence readiness matrix for Market Overview, Liquidity, Rotation, Breadth, Macro, and Scanner Context that counts score-grade, observation-only, missing, and blocked inputs per surface.

### WS-015: Decision Cockpit Regime Is Low Confidence

Likely root cause: Decision Cockpit is downstream of strict regime-driver gates and missing upstream evidence. The engine blocks proxy/fallback/observation-only drivers, requires enough scoring drivers, and intentionally marks some advanced drivers unavailable in v1.

Evidence:

- The regime engine is pure; it does not fetch providers directly.
- Driver trust blocks unsupported freshness/source authority states.
- Missing evidence and confidence cap reasons are surfaced instead of silently increasing confidence.

Confidence: High.

Next diagnostic: after upstream readiness is measured, produce a driver-by-driver cockpit table showing `available`, `blocked`, `missing`, `score-grade`, and confidence-cap reason for every driver.

### WS-029: Liquidity Monitor Includes Only 1 of 49 Indicators

Likely root cause: Liquidity Monitor is cache-only by default and most indicator families either lack real source authority, require official/paid data, or are intentionally observation-only. The service also requires at least three reliable indicators before regime conclusions become available.

Important discrepancy: current static code exposes 12 indicator families and 39 named required inputs, not 49. The exact T-1757 denominator likely came from a rendered response, older coverage matrix, or a broader product checklist. That denominator remains an explicit unknown until a safe local/runtime diagnostic captures the live coverage contract without changing provider/cache state.

Confidence: High for root class; Medium for exact denominator.

Next diagnostic: add or use a safe coverage-matrix response that reports each indicator family, required input, fulfilled input, provider class, real-source availability, proxy-only state, and score eligibility.

### WS-031: Rotation Radar Has No Real Themes for Ranking

Likely root cause: Rotation Radar is correctly quarantining non-authoritative themes. Configured quote provider coverage, feed entitlement, source freshness, constituent coverage, and theme-flow authority must pass before themes enter strongest/accelerating headline lists.

Evidence:

- Fallback/static/taxonomy/synthetic/unavailable themes are visible but excluded from headline ranking.
- Non-US markets are taxonomy-only by design.
- Existing tests assert fallback radar has no external calls, no headline themes, and score contribution disabled.

Confidence: High.

Next diagnostic: validate configured quote-provider coverage and ranking-lane exclusion reasons separately. Do not relax ranking gates until source authority is proven.

### Home Market Briefing

Likely root cause: Home market briefing is a downstream consumer of Market Temperature trust inputs, so it degrades when Market Overview, Liquidity, or Rotation evidence is insufficient. The homepage intelligence endpoint itself is fixture/metadata content and is not a live market evidence source.

Confidence: High.

Next diagnostic: keep Home validation downstream; first fix/measure Market Overview, Liquidity, and Rotation readiness.

### Research Radar Evidence Gaps

Likely root cause: Research Radar depends on authenticated user-scoped scanner/watchlist evidence and does not run providers. `/research/queue` can aggregate market input internally, but the current endpoint only passes scanner/watchlist inputs.

Confidence: High.

Next diagnostic: expose explicit prerequisite readiness for scanner run presence, watchlist overlay presence, and queue source surfaces. If product expects market-derived queue items, add a separate API contract task after review.

## Recommended Implementation Wave

1. Safe diagnostics first: add a provider-free consumer evidence readiness matrix covering Market Overview, Decision Cockpit drivers, Liquidity families, Rotation ranking lanes, Home briefing prerequisites, and Research Radar prerequisites.
2. Reconcile Liquidity denominator: compare T-1757's "49" against current 12-family/39-input static contract and the live response shape using read-only diagnostics only.
3. Provider activation planning: for macro/VIX/rates/Fed liquidity/US breadth/ETF flow/rotation quotes, list the exact source, required authorization, cache path, freshness SLA, and score-authority rule before implementation.
4. Liquidity implementation: activate real-source families one at a time, keeping proxy-only families observation-only until source review approves scoring.
5. Rotation implementation: validate configured quote-provider coverage and feed access, then review ranking quarantine reasons before allowing headline ranking.
6. Cockpit implementation: only after upstream score-grade evidence improves, recalibrate confidence caps and missing-evidence copy.
7. Research/Home contract work: decide whether Research Queue should include market context and whether homepage intelligence remains fixture-only; implement as separate contract/UI tasks.

## Validation Recommendations

Read-only/static validation:

- `git diff --check origin/main...HEAD`
- `git diff --check`
- `python -m pytest tests/api/test_market_intelligence_payload_smoke.py -q`
- `python -m pytest tests/api/test_market_rotation_radar.py -q`
- `python -m pytest tests/test_market_intelligence_smoke_checklist.py -q`

Runtime validation only when a local server is already running and protected-domain approval exists:

- `curl -sS "$API_BASE/api/v1/market/data-readiness?symbols=AAPL,MSFT,SPY"`
- `curl -sS "$API_BASE/api/v1/market/liquidity-monitor"`
- `curl -sS "$API_BASE/api/v1/market/rotation-radar?market=US"`
- `curl -sS "$API_BASE/api/v1/market/decision-cockpit"`

Do not use provider-backed runtime validation until provider/cache boundaries are explicitly approved.

## Parallelization Map

Can run in parallel:

- Static/read-only diagnostics for Market Overview, Liquidity coverage, Rotation ranking reasons, Research prerequisites, and Home contract documentation.
- Frontend copy/empty-state follow-ups once the backend diagnostic shape is stable.
- Test expansion for existing fallback/quarantine behavior.

Must be serial or manual-review:

- Provider auth/feed entitlement validation.
- Cache mutation or cache accounting changes.
- Liquidity provider activation by family.
- Rotation headline-ranking policy changes.
- Decision Cockpit confidence threshold changes.
- Scanner/DB-backed Research Radar evidence generation.

## File Evidence Index

- API router registration: `api/v1/router.py`
- Market Overview routes: `api/v1/endpoints/market_overview.py`
- Market aggregate routes: `api/v1/endpoints/market.py`
- Liquidity route: `api/v1/endpoints/liquidity_monitor.py`
- Research routes: `api/v1/endpoints/research.py`
- Homepage intelligence route: `api/v1/endpoints/homepage_intelligence.py`
- Market Overview service and fallback gates: `src/services/market_overview_service.py`
- Market regime decision engine: `src/services/market_regime_decision_engine.py`
- Liquidity service and provider activation policies: `src/services/liquidity_monitor_service.py`
- Rotation radar service and ranking quarantine: `src/services/market_rotation_radar_service.py`
- Rotation quote provider diagnostics: `src/services/rotation_radar_quote_provider.py`
- Research Radar service: `src/services/research_radar_service.py`
- Research Queue aggregator: `src/services/research_queue_aggregator_service.py`
- Evidence framing: `src/services/market_intelligence_evidence.py`
- Data coverage registry: `src/services/data_coverage_surface_registry.py`
- Local readiness diagnostics: `src/services/market_data_readiness_diagnostics.py`
- Frontend API clients: `apps/dsa-web/src/api/marketOverview.ts`, `apps/dsa-web/src/api/market.ts`, `apps/dsa-web/src/api/marketDecisionCockpit.ts`, `apps/dsa-web/src/api/liquidityMonitor.ts`, `apps/dsa-web/src/api/marketRotation.ts`, `apps/dsa-web/src/api/researchRadar.ts`
- Consumer pages: `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx`, `apps/dsa-web/src/pages/LiquidityMonitorPage.tsx`, `apps/dsa-web/src/pages/ResearchRadarPage.tsx`
- Existing behavior docs: `docs/liquidity/README.md`, `docs/rotation/README.md`
- Existing tests: `tests/api/test_market_intelligence_payload_smoke.py`, `tests/api/test_market_rotation_radar.py`, `tests/test_market_intelligence_smoke_checklist.py`

## Remaining Unknowns

- The exact source of T-1757's "1 of 49" Liquidity denominator is not visible in current static code.
- Live provider configuration, entitlement, quota, cache freshness, and DB scanner contents were not inspected because they are protected-domain boundaries.
- The local server state was not probed because GET routes can cross provider/cache boundaries depending on configuration.
