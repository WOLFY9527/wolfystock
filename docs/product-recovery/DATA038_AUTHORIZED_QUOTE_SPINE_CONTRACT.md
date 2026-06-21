# DATA-038 Authorized Quote Spine Contract

Task ID: DATA-038

Status: docs-only implementation contract. This document does not implement
provider/runtime behavior, provider order, credentials, cache behavior, database
state, API schemas, frontend rendering, scanner scoring, portfolio accounting,
backtest math, factor runtime behavior, live network behavior, or external data
rights.

This contract treats the authorized quote spine as a future bounded market-data
backbone for Scanner, Watchlist, Stock Detail, Portfolio, Market Rotation,
Market Overview, Backtest, Factor Research, and Scenario Lab. It is grounded in
the current repository contracts and intentionally fails closed where source
authority, freshness, coverage, or display rights are missing.

## 1. Executive conclusion

WolfyStock's next professional-platform backbone is not another consumer copy
pass. It is an authorized quote and daily OHLCV spine that can give every
research surface the same bounded answer to: what symbol is this, what market
does it belong to, what price/bar evidence exists, how fresh is it, who is
allowed to use it, and whether it can influence score-grade output.

Current product-recovery docs already identify local quote and daily OHLCV
persistence for a small US/CN/HK acceptance universe as the next core data
dependency after official macro and ETF/index quote authority
(`docs/product-recovery/DATA_COVERAGE_MATRIX.md:376`). DATA-030 names the same
need as an authorized quote spine with delayed or realtime snapshots plus daily
OHLCV for bounded US/CN/HK symbols
(`docs/product-recovery/DATA030_PROFESSIONAL_DATA_SOURCE_ROADMAP.md:19`). DATA-038
turns that roadmap item into the implementation contract future tasks must
follow.

This contract enables:

- one shared quote/OHLCV evidence model instead of per-surface inference;
- score-authority gates that depend on source, freshness, coverage, display
  rights, and degraded-state proof;
- safer Scanner and Rotation ranking eligibility;
- Watchlist and Stock Detail packets with durable quote/history refs;
- Portfolio valuation lineage that distinguishes market prices, broker
  snapshots, and fallback estimates;
- Backtest and Factor Research data-readiness checks that can separate local
  research data from point-in-time or adjusted-data claims;
- Scenario Lab baselines that reference upstream snapshot IDs instead of
  request-only inputs.

This task does not implement:

- new provider calls, feed activation, provider order changes, fallback changes,
  cache TTL/SWR changes, prewarm jobs, or credential diagnostics;
- database tables, migrations, API fields, stored contract versions, frontend
  UI, or runtime wiring;
- pricing-provider changes for Portfolio;
- broker/order paths, portfolio ledger mutations, accounting semantics,
  backtest engine behavior, factor engines, auth, or external network behavior;
- source-authority grants, right-to-display approval, redistribution approval,
  or live environment evidence.

## 2. Current quote and OHLCV state

### US quote paths

US single-stock realtime quotes currently route through
`DataFetcherManager.get_realtime_quote`. When Alpaca credentials are complete,
the manager attempts Alpaca first, then falls back to yfinance. If Alpaca is
partial, absent, failed, empty, or missing basic fields, the trace records that
state and yfinance may be attempted next (`data_provider/base.py:1742`,
`data_provider/base.py:1757`, `data_provider/base.py:1791`,
`data_provider/base.py:1829`). Focused tests verify Alpaca preference, yfinance
fallback, and skipped partial credentials (`tests/test_data_fetcher_manager_alpaca.py:59`,
`tests/test_data_fetcher_manager_alpaca.py:87`,
`tests/test_data_fetcher_manager_alpaca.py:114`).

US index realtime quote routing is narrower: shared US index quote handling is
yfinance-only today (`data_provider/base.py:1683`). That means an ETF/index
quote path used by Market Overview or Rotation cannot be treated as repo-wide
authorized spine proof merely because Rotation has a configured-provider path.

StockService consumes quotes through a narrow provider adapter that projects
price, change, volume, amount, source, and provider timestamp into
`StockServiceQuoteSnapshot` (`src/services/stock_service_provider_adapter.py:10`,
`src/services/stock_service_provider_adapter.py:38`). Stock quote metadata then
classifies placeholder, fallback, timestamp-missing, and provider-runtime states
instead of assuming every price is current evidence (`src/services/stock_service.py:776`).

### US history paths

US daily history uses `DataFetcherManager.get_daily_data`. For US stocks,
Alpaca is considered before yfinance when configured; US index/history also
goes through the controlled US candidate path. Empty provider history or raised
provider errors are traced and fail through to the next candidate or a
`DataFetchError` (`data_provider/base.py:1294`, `data_provider/base.py:1351`,
`data_provider/base.py:1387`, `data_provider/base.py:1449`). Tests cover Alpaca
daily history preference and yfinance fallback
(`tests/test_data_fetcher_manager_alpaca.py:132`,
`tests/test_data_fetcher_manager_alpaca.py:165`).

`StockService.get_history_data` adds a local-first US parquet path and a
persisted local DB fallback. If no usable provider, parquet, or persisted rows
exist, it returns an unavailable daily OHLCV state rather than fabricating bars
(`src/services/us_history_helper.py:138`, `src/services/stock_service.py:209`,
`src/services/stock_service.py:221`). Local US parquet is useful operator data,
but current docs state no checked-in production dataset is authoritative
(`docs/product-recovery/DATA_COVERAGE_MATRIX.md:367`).

### CN quote paths

CN realtime quotes use the configured `realtime_source_priority`, trying
efinance, AkShare Eastmoney, AkShare Sina, Tencent/AkShare QQ, and Tushare as
configured. The first successful source may be supplemented by later sources
for missing fields, and all provider failures are captured in trace entries
(`data_provider/base.py:2001`, `data_provider/base.py:2017`,
`data_provider/base.py:2071`). Provider docs explicitly caution that public
proxy or aggregation sources need explicit source authority per use
(`docs/product-recovery/DATA_COVERAGE_MATRIX.md:162`).

CN cache-only diagnostics exist for CN/HK connect flow and CN money-market
rates, but they are not live quote authority. Provider-data docs state those
paths remain observation-only, do not make live provider calls, and must not
promote static Market Overview fallback rows or Liquidity scoring
(`docs/provider-data/README.md:31`, `docs/provider-data/README.md:46`).

### CN history paths

CN daily history is still provider-chain based through the shared manager and
scanner data managers. Current Scanner gaps list covered universe, quote
snapshot, daily OHLCV, volume/turnover, sector/theme metadata, rejection counts,
and candidate packets as missing or insufficient (`docs/product-recovery/DATA_COVERAGE_MATRIX.md:222`).
Scanner tests exercise local hits and fail-closed history gaps, but there is no
single authorized CN quote spine store yet.

### HK quote paths

HK realtime quotes use a dedicated path: Twelve Data first when configured,
then AkShare HK fallback (`data_provider/base.py:1880`,
`data_provider/base.py:1901`, `data_provider/base.py:1939`). The Twelve Data
adapter supports quote and daily history normalization for HK/US scanner
support, but entitlement, delay, and display rights remain to be verified
(`data_provider/twelve_data_fetcher.py:58`,
`data_provider/twelve_data_fetcher.py:139`,
`data_provider/twelve_data_fetcher.py:164`).

### HK history paths

HK daily history attempts Twelve Data first, then falls back to the existing
fetcher chain (`data_provider/base.py:1463`, `data_provider/base.py:1498`).
Current product docs classify Twelve Data as integrated configuration for HK/US
quote/history fallback with entitlement and delay still unknown
(`docs/product-recovery/DATA_COVERAGE_MATRIX.md:169`).

### ETF and index proxy paths

Rotation Radar has the strongest current ETF/index quote readiness contract. It
uses a configured Alpaca path for 5m/15m/60m/1d OHLCV windows and yfinance
fallback; fallback/static/taxonomy-only data cannot populate headline lanes
(`docs/rotation/README.md:36`, `docs/rotation/README.md:21`).
The service exposes `alpacaQuoteAuthorityReadiness`, provider diagnostics,
coverage, missing symbols, fallback usage, and activation state
(`src/services/rotation_radar_quote_provider.py:1660`,
`src/services/rotation_radar_quote_provider.py:1674`). DATA-021 accepted this
as bounded quote readiness, not target-environment entitlement proof
(`docs/product-recovery/DATA021_REAL_DATA_VALUE_ACCEPTANCE.md:47`).

Market Overview still has yfinance-style quote proxy paths for some index and
volatility panels. Tests assert yfinance proxy rows must not claim live/fresh
status or score contribution when official or authorized evidence is absent
(`tests/test_market_overview_core_quote_repair.py:359`,
`tests/test_market_overview_core_quote_repair.py:385`).

### Fallback, proxy, cache-only, and demo states

Existing repository contracts already separate degraded states:

- fallback/static Rotation themes remain observation lanes and are not
  headline/ranking eligible (`tests/test_market_rotation_radar_service.py:992`,
  `tests/test_market_rotation_radar_service.py:1243`);
- MarketCache is a panel cache, not source authority by itself
  (`docs/product-recovery/DATA_COVERAGE_MATRIX.md:365`);
- cache-only CN/HK flow and CN money-market diagnostics remain
  `observationOnly=true` and `scoreContributionAllowed=false`
  (`docs/provider-data/README.md:41`, `docs/provider-data/README.md:51`);
- Options and Scenario readiness contracts distinguish sample/demo or
  request-supplied inputs from authoritative baseline inputs
  (`docs/product-recovery/DATA021_REAL_DATA_VALUE_ACCEPTANCE.md:103`,
  `docs/product-recovery/DATA021_REAL_DATA_VALUE_ACCEPTANCE.md:121`);
- tests cover source-confidence and provider-freshness fail-closed behavior for
  fallback, mock, synthetic, stale, partial, unavailable, and ambiguous states
  (`tests/test_source_confidence_contract.py:67`,
  `tests/test_provider_freshness_contracts.py:43`).

### Known missing source-authority gaps

The main missing gaps are:

- no durable quote/daily OHLCV snapshot store for the bounded US/CN/HK
  acceptance universe;
- no quote-spine-level `rightToDisplay` or audience/surface display grant;
- no unified snapshot ID shared across Scanner, Watchlist, Stock, Portfolio,
  Market Overview, Rotation, Backtest, Factor Research, and Scenario Lab;
- no consistent adjusted-basis and corporate-action lineage for backtest and
  factor use;
- no target-environment proof that Alpaca, Twelve Data, CN providers, local
  datasets, or yfinance-like proxy rows satisfy entitlement, freshness,
  coverage, display rights, and source authority for each surface;
- no dedicated quote spine snapshot/store test bundle.

## 3. Quote spine requirements

The authorized quote spine must define an additive, fail-closed contract. Every
field below must remain distinct; no field can be inferred from another.

| Requirement | Contract expectation |
| --- | --- |
| Bounded universe | Start with an explicit acceptance universe by market. Each row needs universe version, inclusion reason, active/listing state where available, and missing/unverified status where not. |
| Symbol identity | Canonical symbol, raw provider symbol, display symbol, normalized internal code, optional CIK/ISIN/FIGI-like IDs when available, and symbol-change lineage as a future extension. |
| Market/country/exchange | Market code, country/region, exchange, session calendar family, currency, and ETF/index/security type. Unknown values stay unknown. |
| Quote snapshot | Last price, change amount, change percent, previous close, open/high/low, bid/ask where licensed, volume, turnover/traded value, and snapshot ID. Missing fields stay missing. |
| Daily OHLCV snapshot | Date, open, high, low, close, volume, turnover/traded value, bar count/window, missing-bar count, latest bar date, and snapshot ID. |
| Adjusted basis | Explicit `raw`, `split_adjusted`, `dividend_adjusted`, `total_return`, `unknown`, or `not_integrated` basis. Backtest/factor promotion is blocked unless adjusted-basis methodology is approved. |
| Volume and turnover | Share volume plus traded value/turnover where provider supplies it. Derived turnover must record methodology and cannot replace observed turnover without a derived-data flag. |
| As-of timestamp | Provider timestamp, market/session timestamp, observed-at timestamp, stored-at timestamp, and timezone. A storage timestamp cannot prove market freshness. |
| Delay/freshness state | `live`, `delayed`, `cached`, `stale`, `partial`, `fallback`, `synthetic`, `unavailable`, or `unknown`. `fresh` or `live` may appear only when the underlying contract proves it. |
| Source authority | Surface-specific source authority for the evidence family. Provider labels, cache hits, high coverage, and successful responses are insufficient. |
| Right-to-display | Audience and surface-specific display grant. It must be independent from source authority and score authority. Missing review blocks consumer display or requires a safe unavailable state. |
| Cache lineage | Cache key or snapshot ID, cache layer, TTL/SWR policy when applicable, cache hit/miss/stale state, source snapshot references, and whether cache mutation occurred. Consumer packets should not expose raw cache internals. |
| Stale/missing/fallback/demo state | Explicit degraded-state flags and reason buckets. The strongest safety limitation wins when multiple degraded states apply. |
| Observation-only vs score-authoritative | Every consumer must receive a clear posture: observation-only, score-authoritative for a named path, blocked, unavailable, or not integrated. Score authority requires source, freshness, coverage, display rights, and surface approval. |

Minimum spine shape for future implementation:

```text
contractVersion
snapshotId
symbolIdentity
marketIdentity
quoteSnapshot
dailyOhlcvSnapshot
adjustmentBasis
volumeTurnover
asOf
freshness
sourceAuthority
rightToDisplay
cacheLineage
degradedState
scoreAuthority
consumerProjection
adminDiagnostics
```

Consumer projection must be smaller than admin diagnostics. It may expose
availability, delayed/stale/missing state, as-of time, and a bounded data action.
It must not expose credentials, provider payloads, request IDs, trace IDs, cache
keys, raw source-authority internals, or remediation instructions by default.

## 4. Surface dependency matrix

| Surface | Required quote fields | Minimum freshness | Score-authority gate | Fallback behavior | Product value unlocked |
| --- | --- | --- | --- | --- | --- |
| Market Overview | Index/ETF/security symbol, level/last, change percent, volume where relevant, as-of, source, freshness, source authority, score contribution state. | For market panels: live, delayed, or cached with explicit as-of; official rows may be daily T+1. Stale/proxy rows stay capped. | `sourceAuthorityAllowed=true`, `scoreContributionAllowed=true`, coverage and freshness pass, and right-to-display present for Market Overview. | Proxy/fallback panels may remain visible as observation context but cannot upgrade regime or market-score conclusions. | Market first-read can distinguish real market facts from proxy context and feed cleaner Market Briefing/Decision Cockpit output. |
| Market Rotation / Rotation Radar | ETF/index benchmark price, member price, change percent, relative strength, volume ratio, 5m/15m/60m/1d windows, as-of, fallback flags, headline eligibility. | Rotation quote windows need provider timestamps within the configured radar policy; shared radar snapshot TTL remains separate cache metadata. | Headline lanes require rank eligible, headline eligible, `rankingLane=headline`, source authority, score contribution, coverage, and display rights. | yfinance/static/taxonomy-only themes remain observation/taxonomy lanes and cannot populate strongest/accelerating headline lanes. | Theme leadership can move from taxonomy/proxy evidence to quote-backed participation and trend evidence. |
| Scanner | Universe row, current/pre-open quote where available, daily OHLCV window, volume, turnover, liquidity metrics, latest trade date, blocker bucket, source/freshness state. | Scanner can run with delayed or latest-close facts when explicitly labeled; score-grade candidates need source/freshness/coverage proof for the selected profile. | Candidate score authority requires source authority, score contribution, sufficient history, coverage, no fallback/proxy blocker, and right-to-display. | Missing quote can preserve historical observation rows but must lower confidence and populate blocker buckets; empty runs are valid terminal states. | Scanner becomes a real bridge from market context into symbol research queues. |
| Watchlist | Row symbol, market, quote state, price, change percent, volume if available, as-of, scanner lineage refs, latest packet status. | Open-market rows should have bounded delayed/intraday or latest-close status; saved rows must not infer quote freshness from scanner score recency. | Row packets are observation-only until quote spine source/freshness/display gates pass for Watchlist. Scanner lineage cannot grant quote authority. | Unknown/missing quote stays missing or unknown and contributes to `missingData`; no provider fan-out from row projection. | Saved symbols become a useful research queue with price/update/research status. |
| Stock Detail | Quote snapshot, daily OHLCV summary, structure input quality, price/history as-of, source confidence, missing data buckets, evidence refs. | Quote may be delayed or latest close if labeled; structure needs usable daily OHLCV and should degrade when history is unavailable. | Stock packet readiness requires real quote and history, no synthetic/placeholder state, explicit source/freshness/coverage/display gates, and no raw provider leakage. | Placeholder, timestamp-missing, fallback, stale, or unavailable quote/history produces partial/blocked research state. | Stock page can lead with identity, quote, trend/history, structure, and missing evidence instead of scattered diagnostics. |
| Portfolio | Position price, price source, price as-of, fallback flag/reason, FX rate/as-of, valuation snapshot ID, benchmark/factor refs. | Daily close, broker snapshot, or delayed quote may be usable only with explicit source/as-of; stale FX or price gaps downgrade valuation lineage. | Price lineage is score-authoritative only when price and FX are complete, current by policy, source-authorized, display-approved, and analytics readiness passes. | Avg-cost fallback, stale FX, missing quote, or broker-only snapshot stays disclosed and observation-only; ledger math is unchanged. | Holdings valuation, P&L, exposure, and structure review become credible without mutating accounting semantics. |
| Backtest | Historical OHLCV bars, adjusted basis, bar count, missing dates, stale-bar policy, point-in-time universe refs, dataset version, source/as-of lineage. | Backtest professional use requires historical snapshot reproducibility, PIT/as-of policy, and approved stale-bar policy, not realtime quote freshness. | Current backtest readiness/provenance is diagnostic-only. Score-grade backtest/factor outputs require approved adjusted data, PIT universe, calendar, and source authority. | No silent live provider fallback; missing bars, local-only rows, synthetic stress paths, or ambiguous lineage block professional readiness. | Backtest can graduate from research-useful v1 semantics toward reproducible institutional-style data readiness without changing engine math prematurely. |
| Factor Research | Derived factor observations, price/return basis, exposure value, as-of, observed-at, source name/type, freshness, fallback/stale/partial flags, forward-return lineage. | Factor observations require explicit `as_of` and observed-at; fallback/stale observations cannot become fresh/live factor evidence. | `professionalReady` only when every tracked prerequisite is explicit; otherwise factor packets remain observe-only. | Missing or ambiguous factor panel, forward return, neutralization, or source lineage blocks readiness. | Factor exposure, neutralization, IC, bucket, and long-short research can cite a shared data lineage instead of caller-supplied ambiguity. |
| Scenario Lab | Upstream market frame, baseline snapshot ID, quote-derived drivers, evidence states, score authority, source authority, last updated, stale driver flags. | Scenario baseline needs enough score-grade market drivers and non-stale market frame; request-supplied/sample states remain observation-only. | Authoritative scenario baseline requires upstream quote/macro/portfolio snapshots with source, freshness, coverage, display rights, and score authority. | Fixture/static/request-supplied inputs stay observation-only; missing drivers make scenario partial or unavailable. | Scenario outputs can compare stored market/portfolio baselines under bounded shocks with explicit input lineage. |

## 5. Implementation options

### Provider adapter direct read

Pros:

- smallest initial runtime footprint;
- reuses existing DataFetcherManager, StockService, Rotation provider, and
  provider traces;
- useful for targeted probes and operator evidence.

Cons:

- consumers can fan out to providers independently;
- repeated reads can diverge by time, provider route, or fallback path;
- no durable snapshot ID for Scanner/Watchlist/Portfolio/Backtest joins;
- hard to prove replay, audit, or right-to-display after the call.

Protected-domain risk:

- high risk for provider order, fallback, credentials, live-call paths, budgets,
  cache behavior, and external network behavior.

Validation requirements:

- provider routing tests, credential diagnostics tests, no network in default
  tests, failure-class tests, no raw provider leakage, source-confidence tests,
  and surface-specific score-authority tests.

Private-beta suitability:

- suitable only for controlled probes or admin diagnostics, not as the main
  quote spine for score-grade surfaces.

### Durable DB snapshot

Pros:

- stable snapshot IDs and replayable as-of joins;
- supports Scanner, Watchlist, Stock, Portfolio, Backtest, Factor, and Scenario
  consumers from one source of truth;
- can store source/freshness/coverage/display-rights metadata beside data;
- best path for audit, backtest/factor reproducibility, and target-environment
  evidence.

Cons:

- needs schema design, migrations, write policies, retention, and invalidation;
- can touch protected storage and provider runtime domains;
- requires careful owner review for portfolio and backtest consumers.

Protected-domain risk:

- high risk for DB/storage, migrations, provider cache/runtime, portfolio
  valuation reads, and backtest/factor source-of-truth semantics.

Validation requirements:

- migration tests, snapshot write/read tests, idempotency, retention, source
  authority fail-closed tests, no synthetic/fallback promotion tests, consumer
  projection tests, and replay/as-of tests.

Private-beta suitability:

- best medium-term private-beta foundation after docs/contracts and offline
  fixture tests are approved.

### Local file artifact

Pros:

- simple for operator-supplied acceptance universe snapshots;
- works well for local/offline backtest and factor fixture development;
- avoids immediate DB migrations.

Cons:

- environment-dependent paths and stale-file risk;
- weak multi-user and multi-surface coordination;
- hard to enforce display rights and cache lineage consistently;
- local presence can be mistaken for source authority unless guarded.

Protected-domain risk:

- medium risk for local dataset semantics, backtest data lineage, and accidental
  environment-specific path assumptions.

Validation requirements:

- file schema validation, path sanitization, stale/missing/permission-denied
  tests, no provider fallback tests for local-only lanes, and source-authority
  negative tests.

Private-beta suitability:

- useful for bounded offline pilots, not enough for shared product surfaces by
  itself.

### Cache-first snapshot

Pros:

- reuses MarketCache-style panel concepts and existing freshness vocabulary;
- can reduce provider load for market surfaces;
- useful for latest market state when DB persistence is not yet ready.

Cons:

- cache hit is not source authority;
- cache TTL/SWR behavior is protected and surface-specific;
- not enough for Backtest/Factor reproducibility or Portfolio audit lineage;
- stale/fallback cache rows can be overread by downstream consumers.

Protected-domain risk:

- high risk for MarketCache TTL, SWR, cold-start, cache key, background refresh,
  fallback, and payload meaning.

Validation requirements:

- cache hit/stale/fallback tests, no authority-from-cache tests, cache lineage
  projection tests, and consumer-safe metadata tests.

Private-beta suitability:

- useful as a read-through layer only when paired with explicit source/freshness
  gates; insufficient as the sole spine.

### Hybrid DB summary plus cache detail

Pros:

- DB stores durable normalized summary, source/freshness/display-rights state,
  and snapshot IDs;
- cache can retain provider-specific detail for recent market views;
- consumers can join by snapshot ID while admin tools inspect cache diagnostics;
- balances auditability and operational cost.

Cons:

- more complex ownership boundary;
- requires strict separation between consumer summary and admin detail;
- needs clear invalidation and backfill policy.

Protected-domain risk:

- high but manageable if split into serial tasks: contract, DB summary, cache
  detail, then surface consumption.

Validation requirements:

- all durable snapshot tests plus cache lineage tests, consumer/admin field
  separation tests, stale/fallback/missing downgrade tests, and per-surface
  authority tests.

Private-beta suitability:

- recommended target architecture for private beta after a contract-first and
  fixture-first sequence.

## 6. Recommended implementation sequence

Recommended follow-up DATA tasks:

| Task | Outcome | Parallelization |
| --- | --- | --- |
| DATA-039 Quote spine fixture and authority schema | Define inert fixture contract for bounded universe, quote snapshot, daily OHLCV, adjusted basis, freshness, source authority, right-to-display, cache lineage, and degraded state. | Serial first. This freezes the contract other tasks consume. |
| DATA-040 Source/display authority proof matrix | Add source-family and surface matrix for US/CN/HK providers, yfinance/proxy, local files, cache-only diagnostics, and right-to-display review state. | Can run in parallel with DATA-041 after DATA-039 shape is stable. |
| DATA-041 Quote spine snapshot store design | Design durable DB summary plus optional cache-detail boundary, retention, snapshot IDs, replay/as-of policy, and no provider runtime change plan. | Serial with storage/migration work; design can run parallel with DATA-040. |
| DATA-042 Rotation and Market Overview quote-spine adapter plan | Map existing Alpaca/yfinance ETF/index readiness and Market Overview proxy panels into the spine without changing provider order. | Parallel with DATA-043 if no shared files are edited. |
| DATA-043 Scanner/Watchlist/Stock packet consumption plan | Define how row packets and stock research packets reference quote/history snapshot IDs and fail closed when refs are missing. | Parallel with DATA-042 after DATA-039. |
| DATA-044 Portfolio valuation lineage integration plan | Define price/FX/snapshot lineage reads from quote spine without changing ledger, cost basis, broker sync, or pricing provider order. | Must serialize with any portfolio implementation; plan can follow DATA-039. |
| DATA-045 Backtest and Factor data-readiness bridge | Define adjusted basis, PIT universe, stale-bar, forward-return, and factor panel lineage requirements before consuming quote spine. | Serial for contract; implementation must wait for DATA-041 and backtest owner review. |
| DATA-046 Scenario baseline snapshot integration plan | Define Scenario Lab baseline snapshot IDs that reference quote spine, macro/risk, and portfolio snapshot lineage. | Depends on DATA-041 and DATA-044; should not start implementation before upstream snapshot contracts exist. |

Parallel guidance:

- DATA-040 and DATA-041 design can run in parallel only if neither edits shared
  schema or storage code.
- DATA-042 and DATA-043 can run as read-only or docs/planning tasks in parallel
  after DATA-039.
- Portfolio, Backtest, Factor, Scenario, DB migrations, provider runtime,
  MarketCache, and pricing-provider changes must be serialized.

## 7. Fail-closed rules

- No synthetic quotes: fixture, placeholder, generated, inferred, or sample rows
  cannot become quote or OHLCV evidence for product scoring.
- No fake freshness: delayed, cached, stale, fallback, partial, unavailable, or
  unknown data cannot be relabeled as live or fresh without explicit freshness
  proof.
- No hidden fallback promoted as authoritative: fallback provider rows, static
  baskets, yfinance proxy rows, local-only files, and cache-only diagnostics
  must preserve their degraded state.
- No provider label as proof: Alpaca, Twelve Data, Tushare, AkShare, Efinance,
  yfinance, local parquet, Polygon, broker sync, or any future provider label is
  not enough to grant authority.
- No cache hit as proof: MarketCache, provider cache, local DB, parquet, or
  snapshot availability proves storage availability only, not source authority
  or display rights.
- No score authority without source/freshness/coverage/right-to-display:
  `scoreContributionAllowed=true` must require source authority, freshness,
  coverage, degraded-state checks, display approval, and surface-specific
  authorization.
- No frontend or consumer inference: Watchlist, Stock Detail, Scanner, Market
  Overview, Rotation, Portfolio, Backtest, Factor, and Scenario consumers must
  read explicit spine posture instead of recomputing authority from raw fields.
- No raw leakage: default consumer routes must not expose provider payloads,
  credentials, env names, raw diagnostics, request IDs, trace IDs, cache keys,
  internal source-authority fields, or remediation details.
- No consumer advice: quote spine data can support research facts, evidence
  gaps, readiness states, and next data actions only. It must not create
  personalized action instructions, broker/order language, price-objective
  claims, risk-order instructions, or position-allocation instructions.

## 8. Acceptance checklist

Before the quote spine can be used for score-grade Scanner, Portfolio,
Rotation, Backtest, or Factor outputs, evidence must show:

- bounded universe:
  - explicit US/CN/HK symbol universe version;
  - active/listing and market/exchange metadata where available;
  - unsupported and unknown symbols fail closed.
- symbol identity:
  - canonical symbol mapping and market identity are deterministic;
  - provider symbols are recorded separately from consumer symbols;
  - symbol changes or missing identity do not silently merge rows.
- quote snapshot:
  - price, change, volume, turnover, as-of, and source metadata are stored or
    explicitly missing;
  - missing price, timestamp-missing price, placeholder, fallback, stale, and
    proxy rows cannot become available score evidence.
- daily OHLCV:
  - open/high/low/close/volume/turnover rows have latest bar date, bar count,
    missing-bar policy, and source lineage;
  - local file or local DB presence is not treated as authority by itself.
- adjusted basis:
  - raw versus adjusted basis is explicit;
  - corporate-action and adjustment methodology gaps block Backtest and Factor
    score-grade use.
- freshness and delay:
  - each market and surface has a documented freshness policy;
  - provider timestamp, observed-at, stored-at, and cache state are separate;
  - stale and delayed states are visible to the gate.
- source authority:
  - source authority is explicit for each evidence family and surface;
  - provider labels, cache hits, coverage, and success responses do not grant
    authority.
- right-to-display:
  - audience/surface display grant is explicit;
  - missing display rights blocks consumer display or returns a safe unavailable
    state.
- cache lineage:
  - cache hits, stale cache, fallback cache, snapshot ID, and source snapshot ID
    are recorded;
  - cache internals stay out of default consumer projections.
- degraded state:
  - fallback, stale, partial, synthetic, unavailable, unknown, and demo/sample
    states fail closed;
  - the strongest safety limitation wins when multiple limitations apply.
- surface gates:
  - Scanner candidates require quote/history/source/coverage/freshness gates
    before score-grade ranking;
  - Portfolio valuation lineage requires price and FX completeness without
    mutating ledger/accounting semantics;
  - Rotation headline lanes require rank/headline eligibility plus quote spine
    authority;
  - Backtest outputs require PIT universe, adjusted data, calendar/session, and
    reproducible snapshot lineage before professional-readiness claims;
  - Factor outputs require factor panel, forward return, neutralization,
    correlation, and source lineage before score-grade factor claims.
- tests:
  - focused quote spine fixture tests;
  - provider/source confidence fail-closed tests;
  - no synthetic/fallback/demo promotion tests;
  - right-to-display missing tests;
  - consumer/admin projection separation tests;
  - per-surface integration tests for Scanner, Watchlist, Stock, Rotation,
    Market Overview, Portfolio, Backtest, Factor, and Scenario;
  - no-advice and raw-diagnostic grep/tests for consumer-visible changes.
- operator evidence:
  - sanitized credential/feed/entitlement evidence for target environments;
  - no secrets, tokens, raw credentials, cookies, or provider payloads in docs,
    logs, commits, or consumer responses.

Until that checklist passes, quote spine work may be diagnostic, observation
context, or read-only planning only.
