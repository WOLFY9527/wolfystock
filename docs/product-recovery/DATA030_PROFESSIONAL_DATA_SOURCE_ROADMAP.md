# DATA-030 Professional Data Source Roadmap

Task ID: DATA-030

Status: docs-only roadmap. This document does not approve or implement provider
runtime changes, provider order changes, credential changes, cache behavior,
schema changes, migrations, frontend rendering, scoring changes, or live network
calls.

Discovery note: no `DATA-017` through `DATA-024` product-recovery files were
present in this worktree during discovery. This roadmap therefore uses the
current product-recovery baseline, DATA-011 / DATA-016 acceptance notes, the
surface map, data/provider docs, and current surface contracts as the grounding
set.

## 1. Executive conclusion

WolfyStock's next professional-platform step is not more generic UI work. The
next step is a real-data acquisition and integration wave that gives each
consumer surface durable, fresh, permission-reviewed, source-authorized market
and security facts.

The current repository already has broad route and contract coverage. The
existing data coverage matrix states that Market Overview, Scanner, Watchlist,
Stock Structure, Portfolio, Scenario Lab, Liquidity Monitor, Rotation Radar, and
Options Lab routes or contracts exist, but many surfaces still lack score-grade
data, local snapshots, freshness metadata, source authority, or a consumer packet
that combines existing facts (`docs/product-recovery/DATA_COVERAGE_MATRIX.md:25`).
DATA-011 and DATA-016 show that first-read UI and packet consumption have become
much safer and more useful, but those passes did not make unavailable provider
families real (`docs/product-recovery/DATA011_PACKET_CONSUMPTION_ACCEPTANCE.md:7`,
`docs/product-recovery/DATA016_FOCUSED_ACCEPTANCE.md:85`).

Must-have real data:

- Official or authorized risk/macro bundle: VIX, rates, Fed liquidity, credit
  stress, USD pressure, and freshness rules.
- Authorized quote spine: delayed or realtime quote snapshots plus daily OHLCV
  for a bounded US/CN/HK acceptance universe.
- Scanner-ready universe/profile/history/quote snapshots and blocker buckets.
- Watchlist and Stock research packets backed by quote, history, event, filing,
  fundamental, peer, and benchmark evidence where available.
- Portfolio valuation lineage: position price source, FX freshness, benchmark
  mapping, factor exposure, and daily snapshots.
- Options chain authority: chain, bid/ask/last, volume, OI, IV, Greeks,
  multiplier, delay/entitlement, redistribution, and methodology proof before
  any gamma-family output is promoted.

Nice-to-have UI polish:

- More badges, copy refinements, generic empty states, or visual reshuffling.
- Additional diagnostic strips explaining missing authority.
- Secondary surface polish before the core data spine is useful.

Professional value comes from converting "route exists but data is missing" into
"research surface has real, bounded, current, reviewable evidence." UI work
should follow those data integrations, not substitute for them.

## 2. Surface-by-surface data gap matrix

| Surface | Current usable data | Current missing data | Gap type | Stale/fallback/demo/observation-only risk | Score-authority boundary | Product value unlocked |
| --- | --- | --- | --- | --- | --- | --- |
| Market Overview | Panel routes, temperature, briefing, market-overview panels, VIX/rates/macro contracts, cache behavior, and first-read synthesis already exist (`docs/codex/WOLFYSTOCK_SURFACE_MAP.md:15`, `docs/product-recovery/DATA_COVERAGE_MATRIX.md:113`). | Official fresh VIX, complete Treasury/FRED/Fed liquidity bundle, authorized index/ETF quotes, broad-market breadth, real flow, durable market facts store. | Mostly backend/provider integration, then limited frontend consumption of new consumer-safe facts. | Proxy volatility, yfinance-style index rows, cache-only rows, stale macro rows, and quote-derived flow must remain capped or observation-only. | A provider name, cache hit, or successful response is not enough; source authority, freshness, coverage, and right-to-display must pass (`docs/data-reliability/provider-source-confidence-contract.md:27`). | Market state can move from generic readiness language to a credible regime/risk first read. |
| Market Rotation / Rotation Radar | Route and API are present. US Rotation can use configured Alpaca quote windows with yfinance fallback, and DATA-016 made readiness labels provider-neutral (`docs/rotation/README.md:36`, `docs/product-recovery/DATA016_FOCUSED_ACCEPTANCE.md:35`). | Authorized ETF/index quote windows, official ETF/index membership and weights, sector/industry mapping, broader theme constituent coverage, breadth/correlation snapshots. | Backend/provider integration first; frontend can already consume headline/observation lanes. | Fallback/static/taxonomy-only themes are visible only for observation and cannot populate headline or strongest-theme lanes (`docs/rotation/README.md:21`). | Headline/rank eligibility requires real-data quote coverage and explicit source authority; ETF proxies remain relative-strength proxies, not real flow (`docs/rotation/README.md:24`). | Rotation can rank themes from real quote participation instead of taxonomy/proxy evidence. |
| Scanner | Real backend workflow, persisted runs/candidates, data-readiness UI, and candidate packet display exist (`docs/product-recovery/DATA_COVERAGE_MATRIX.md:220`, `docs/product-recovery/DATA011_PACKET_CONSUMPTION_ACCEPTANCE.md:17`). | Covered symbol universe, quote snapshots, daily OHLCV windows, volume/turnover, profile metadata, local rejection counts, reusable candidate evidence packet. | Backend/provider integration and persistence; frontend consumption is mostly ready after DATA-011. | Empty runs are valid terminal states when universe, quotes, history, or source gates reject candidates (`docs/product-recovery/DATA_COVERAGE_MATRIX.md:76`). Demo/static candidates must not appear as live output. | Candidate ranking must not be inflated when source contribution is blocked; scoring semantics are protected (`docs/scanner/README.md:26`). | Scanner becomes the real bridge from Market Overview into symbol research queues. |
| Watchlist | Saved-symbol rows, scanner lineage, row research packet consumption, and research overlay exist (`docs/product-recovery/DATA011_PACKET_CONSUMPTION_ACCEPTANCE.md:18`). | Durable row quote, quote as-of, volume, freshness/delay/source authority, event/catalyst age, filing/news refs, latest Stock packet status, persisted row packet lineage. | Backend/provider integration and packet persistence. Frontend consumption is already partially wired. | Watchlist rows must not infer readiness from scanner/backtest diagnostics; missing data stays missing. | Row packets must hide provider/cache/runtime/source-authority internals and stay fail-closed (`docs/product-recovery/SYMBOL_RESEARCH_PACKET_CONTRACT.md:197`). | Saved symbols become a professional research queue instead of a list of names and lineage metadata. |
| Stock Detail | Structure decision, quote, history, evidence, and research packet consumption exist; current Stock page can render a compact readiness snapshot (`docs/product-recovery/DATA011_PACKET_CONSUMPTION_ACCEPTANCE.md:19`). | Safe profile snapshot, durable quote/history refs, fundamentals, statements, SEC/company filings, news/events, catalyst age, peer benchmark, sector/industry, normalized cross-market packet store. | Both: backend/provider integration for missing evidence families, plus frontend/page assembly for any newly added packet fields. | Structure analysis remains observation-only and depends on daily OHLCV; fundamentals/events can be partial or absent. | The symbol packet must use existing data, fail closed, and never make missing data look complete (`docs/product-recovery/SYMBOL_RESEARCH_PACKET_CONTRACT.md:21`). | Stock Detail can become a minimum professional company research packet instead of a structure-only panel. |
| Portfolio | Account, holdings, ledger, cash, broker sync, FX, snapshot, structure review, history, imports, scenario risk, and research-state preview exist (`docs/product-recovery/DATA_COVERAGE_MATRIX.md:323`, `docs/product-recovery/DATA016_FOCUSED_ACCEPTANCE.md:43`). | Position price lineage, quote freshness, official/authorized FX, benchmark mapping, factor mapping, corporate-action quality, broker-sync provenance, daily snapshot invalidation. | Backend/provider/read-model integration. Frontend should not recalculate accounting or price authority. | Average-cost fallback, stale FX, missing quotes, or broker snapshots must be disclosed as valuation limits, not live market truth. | Portfolio UI must distinguish live quote snapshots, broker-sync snapshots, and avg-cost estimates without changing accounting math (`docs/portfolio/README.md:21`). | Portfolio can show credible exposure, risk, and P&L attribution for private-beta users with real holdings. |
| Options Lab | Options Lab shell, normalizers, observation contracts, and first-read UI exist (`docs/codex/WOLFYSTOCK_SURFACE_MAP.md:24`, `docs/options/README.md:19`). | Authorized options chain, IV, OI, volume, Greeks, multiplier, spot, delay, entitlement, redistribution, decision-use, methodology, coverage thresholds. | Provider rights/procurement plus backend/provider/cache contract first; frontend remains observation-only until proof exists. | Current options market-structure outputs are explicitly observation-only and decision-grade blocked (`docs/options/options-market-structure-observation-contract.md:111`). | No provider may be market-structure authority without entitlement, redistribution, decision-use, provenance, freshness, coverage, and manual verification proof (`docs/options/options-market-structure-prerequisite-manifest.md:46`). | Options Lab can graduate from a bounded lab to a real market-structure research surface without pretending chain data exists. |
| Scenario Lab | Backend contract and first-read summary exist (`docs/codex/WOLFYSTOCK_SURFACE_MAP.md:23`, `docs/product-recovery/DATA016_FOCUSED_ACCEPTANCE.md:57`). | Stored baseline market snapshots, Portfolio input snapshot IDs, official VIX/rates/liquidity, FX, cross-asset regime inputs, deterministic run records. | Backend/read-model integration; frontend already has a safer summary pattern. | Without authoritative baseline inputs, Scenario Lab must remain bounded/explanatory. | Scenario output should reference stored input snapshots and not imply execution readiness (`docs/product-recovery/DATA_COVERAGE_MATRIX.md:333`). | Scenario Lab can compare real market/portfolio states under bounded shocks instead of only explaining prerequisites. |

## 3. Professional data source classes

| Source class | Required professional fields | Main surfaces | Current state | Integration stance |
| --- | --- | --- | --- | --- |
| Real-time/delayed quotes | last, bid/ask where allowed, change, percent change, volume, as-of, delay, venue/feed, source authority | Market Overview, Rotation, Scanner, Watchlist, Stock, Portfolio | Partial across adapters; durable authority snapshots missing (`docs/product-recovery/DATA_COVERAGE_MATRIX.md:130`). | First professional spine after official risk bundle; start with bounded symbols and explicit delay labels. |
| ETF/index/sector proxies | ETF/index quote windows, benchmark mapping, sector/theme membership, constituent coverage, proxy limitations | Market Overview, Rotation, Portfolio, Stock | Alpaca-first Rotation path exists; official membership/weights missing (`docs/product-recovery/DATA_COVERAGE_MATRIX.md:123`). | Use for relative-strength observation first; do not treat proxy as real flow or official sector authority. |
| Fundamentals | valuation, profitability, growth, ratios, period, source, restatement/freshness | Stock, Watchlist, Research Radar, Portfolio | Existing FMP/Finnhub/Alpha Vantage/CN paths are fragmented and partial (`docs/product-recovery/DATA_COVERAGE_MATRIX.md:142`). | Normalize by period/source and fail closed on missing point-in-time or rights proof. |
| Earnings/calendar/events | earnings dates, report time, expected/actual fields where licensed, corporate events, dividends, splits, event as-of | Stock, Watchlist, Scanner, Research Radar, Options | No proven product calendar feed (`docs/product-recovery/DATA_COVERAGE_MATRIX.md:146`). | Add event store before using events for research priority. |
| News and filings | headline, source, timestamp, citation, filing accession/ref, event type, stale handling | Stock, Watchlist, Research Radar | News/search exists in reports; SEC parser exists but live official cache is not proven (`docs/product-recovery/DATA_COVERAGE_MATRIX.md:97`). | Official filings first for US; news remains citation-backed context, not market-data authority. |
| Macro series | VIX, Treasury curve, SOFR/DFF, Fed liquidity, credit stress, CPI/PPI, USD pressure | Market Overview, Liquidity, Scenario | Official macro contracts exist; activation needs fresh rows and complete bundles (`docs/data/market-source-activation-blueprint.md:95`). | Serial activation: VIX, then rates/Fed liquidity, then broader bundle. |
| FX | spot/rate, as-of, source, pair mapping, portfolio currency rules | Portfolio, Market Overview, Scenario | Partial market/portfolio FX paths; official/authorized lineage missing (`docs/product-recovery/DATA_COVERAGE_MATRIX.md:140`). | Daily official or authorized FX is enough for valuation snapshots; intraday FX is optional. |
| Options chains | underlying, expiration, strike, side, bid/ask/last, volume, OI, IV, Greeks, multiplier, spot, entitlement, delay | Options Lab, Stock, Scenario | Normalizer can represent fields, but no live authorized provider is proven (`docs/product-recovery/DATA_COVERAGE_MATRIX.md:149`). | Provider proof and rights first; UI and analytics second. |
| IV surface / Greeks / OI / volume | per-contract IV, full Greeks, OI, volume, coverage, stale policy, methodology | Options Lab | Missing as authoritative input (`docs/options/options-market-structure-observation-contract.md:46`). | Must include field-level coverage and delayed/stale downgrades. |
| Breadth | advancers/decliners/unchanged, A/D ratio, highs/lows, coverage denominator, market/session | Market Overview, Liquidity, Rotation | CN breadth and US breadth contracts/Polygon adapter exist, but authority/coverage must pass (`docs/data/market-source-activation-blueprint.md:97`). | Add breadth proof after VIX/rates/quote spine. |
| Flows | ETF/fund flow, CN/HK connect flow, issuer/creation-redemption data, volume-derived proxy labels | Liquidity, Rotation, Market Overview | Current flow proxies are observation-only; CN/HK flow is cache-only diagnostic (`docs/liquidity/README.md:42`, `docs/provider-data/README.md:34`). | Real flow requires separate licensed/authorized source review. |
| Positioning | COT futures positioning, ETF ownership/holdings, short interest, dealer/customer categories where licensed | Market Overview, Scenario, Options | Not integrated as a normalized product source. | Treat as EOD/weekly regime context; do not mix with trade instructions. |
| Gamma/GEX/gamma flip/vanna/charm/zero-DTE/dealer positioning | chain, OI, gamma, IV surface, spot, multiplier, expiry buckets, sign assumptions, methodology version, rights | Options Lab | Prerequisite manifest only; no implementation approved (`docs/options/options-market-structure-prerequisite-manifest.md:1`). | Defer until options chain rights and methodology are approved. |
| Cross-asset regime data | rates, USD, commodities, crypto, volatility, breadth, liquidity, sector leadership, correlations | Market Overview, Liquidity, Scenario, Portfolio | Some cached panels exist; source families are uneven. | Build from authoritative family snapshots, not from raw panel availability alone. |
| Risk/official source bundles | official VIX/rates/Fed liquidity, credit stress, release calendars, source/freshness proofs | Market Overview, Liquidity, Scenario | Highest priority in existing activation blueprint (`docs/data/market-source-activation-blueprint.md:11`). | This is the first professional credibility layer. |

## 4. Provider/integration candidates

Candidate labels below are not approval. They identify source classes to review.
Every candidate needs entitlement, freshness, coverage, right-to-display, cache
policy, and fail-closed tests before it can support score-authoritative output.

| Candidate / source class | Data it may provide | Expected freshness tier | Permission/cost considerations | Likely complexity | Benefiting surfaces | Score-authoritative support | Fallback / observation-only implication |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FRED / Treasury / Fed official-public macro bundle | VIXCLS, Treasury rates, SOFR/DFF, Fed liquidity, credit stress, macro rows | Daily T+1 for many series; weekly T+7 for Fed liquidity | Official/public access; API/rate policy and cache runbook still required | Medium because cache readiness and bundle completeness matter | Market Overview, Liquidity, Scenario, Home, Decision Cockpit | Yes, after freshness/source metadata and required-series coverage pass | Missing or stale series fail closed; partial bundle cannot become score-grade. |
| Alpaca US stock/ETF market-data feed | US stock and ETF quotes/history; Rotation bounded ETF windows | Realtime or delayed depending feed/plan; intraday windows | Key and feed entitlement required; plan and data rights must be verified | Medium for bounded ETF probe; high for broad universe expansion | Rotation, Market Overview, Scanner, Watchlist, Stock, Portfolio | Potentially, only after credential/feed/freshness/coverage/right-to-display proof | yfinance/public proxy fallback remains delayed/proxy observation. |
| Polygon / Massive-style market data | US quotes, aggregates, options, forex, crypto, computed breadth from grouped daily rows | Realtime/delayed/EOD depends on product and plan | Key/paid-plan likely for professional breadth/options; license review required | Medium for breadth proof; high for options/full market data | Market Overview, Liquidity, Scanner, Rotation, Options | Potentially for specific licensed families after coverage and rights proof | If coverage thresholds fail, output remains missing or observation-only. |
| Tiingo / Nasdaq Data Link / IEX-category vendors | US EOD/intraday prices, reference data, news/fundamentals depending vendor | EOD to intraday depending plan | Key/paid tiers; redistribution and derived-data rights vary | Medium | Quote spine, Scanner, Stock, Portfolio, Rotation | Possible after field-level contract and rights review | Candidate only; absence of adapter means no score use now. |
| Tushare Pro / AkShare / Efinance / Baostock / Pytdx source classes | CN quotes/history, boards, fundamentals, announcements, universe | Realtime-like public proxy to EOD depending source | Tushare requires authenticated access/points; public scrapers have stability/authority risk | Medium, because authority classification is uneven | Scanner, Watchlist, Stock, Market Overview | Tushare-like reviewed data may support some families; public proxy rows need caution | Public/proxy data should be capped unless source authority is explicit. |
| Twelve Data / HK quote class | HK/US quote and history fallback | Delayed/realtime by plan | Key/paid-plan unknown; entitlement and delay must be verified | Medium | HK Scanner, Watchlist, Stock, Portfolio | Possible only after HK field coverage and rights proof | Without proof, use as delayed/fallback context only. |
| FMP / Finnhub / Alpha Vantage fundamentals class | Fundamentals, statements, metrics, earnings/calendar/news depending vendor | Daily, quarterly, filing/event cadence; some intraday news | Key and plan limits; point-in-time, redistribution, and historical depth must be reviewed | Medium for normalized packet; high for point-in-time history | Stock, Watchlist, Research Radar, Scanner, Portfolio | Possible for fundamentals only after period/source/rights checks | Missing fields stay `not_integrated` or partial; do not synthesize ratios. |
| SEC EDGAR official companyfacts / filings | US company facts, filings, accession refs, official filing metadata | Filing/day-of with fair-access constraints | Official public; user-agent, caching, and rate policy required | Medium | Stock, Watchlist, Research Radar | Strong for US filings/facts after live cache and citation proof | Parser-only payloads remain observation-only until live cache is implemented. |
| News/search providers and official exchange/company feeds | News headlines, catalysts, regulatory announcements, calendars | Intraday for news; same-day for filings/events | API keys and licensing vary; public search is not a data authority | Medium to high because citation and de-duplication matter | Stock, Watchlist, Scanner, Research Radar | Usually no for scoring unless source and rights are reviewed; yes for cited event context | News may inform research priority but must not create fake confidence. |
| Official ETF issuer / index provider holdings | ETF holdings, index constituents, weights, effective dates | Daily for ETF holdings, scheduled for index changes | Public issuer files or paid official index data; redistribution must be checked | Medium/high due mapping and versioning | Rotation, Portfolio, Stock, Scanner | Yes for membership/benchmark authority after rights proof | ETF proxy quotes without membership remain relative-strength observation. |
| Authorized breadth provider | Advancers/decliners, highs/lows, A/D ratios by market/session | Same session delayed or EOD | Usually paid/authorized; coverage denominator and license review required | Medium | Market Overview, Liquidity, Rotation | Yes after coverage/freshness gates | Representative ETF samples are not broad breadth. |
| Authorized flow provider | ETF/fund flows, creations/redemptions, institutional flow categories | EOD to daily; intraday rare/expensive | Paid/licensed; redistribution and derived-output rights are material | High | Liquidity, Rotation, Market Overview, Portfolio | Yes only after explicit reviewed allowlist | Quote-derived flow proxies remain observation-only. |
| CFTC COT / exchange positioning source class | Futures positioning, managed-money/commercial categories, report date | Weekly | Official/public for COT; mappings and delay must be explicit | Medium | Market Overview, Scenario, Cross-asset regime | Observation-to-score possible only for regime context after methodology review | Weekly lag must be visible; never live positioning. |
| Cboe/OPRA vendor, ORATS, Intrinio, Polygon Options, Tradier class | Options chain, IV, Greeks, OI, volume, expirations, calendars | Realtime/delayed/EOD by entitlement; OI often daily | Paid/licensed; OPRA/vendor redistribution, display, derived-data, and decision-use rights are central | High | Options Lab, Stock, Scenario | Not until proof bundle and methodology gates pass | Fixture/stub/dry-run/options-normalizer output remains blocked. |
| FX/commodity official or authorized sources | FX rates, DXY/commodity proxies, gold/oil, as-of, source | Realtime/delayed for market feeds; daily official alternatives | Vendor or official-public by series; portfolio valuation needs clear as-of policy | Medium | Portfolio, Market Overview, Scenario | Yes for valuation/risk only after pair/source/freshness mapping | Stale FX must cap valuation confidence. |
| Cross-asset/official risk bundle | Composite of official macro, quotes, breadth, FX, commodities, crypto, volatility | Mixed; family-specific | Requires separate authority per family; composite cannot upgrade weak inputs | High | Market Overview, Liquidity, Scenario, Portfolio | Yes only when every required family contributes with explicit authority | Composite must preserve weakest-family limitation. |

Official and vendor references used for candidate framing:

- FRED series observations API:
  <https://fred.stlouisfed.org/docs/api/fred/series_observations.html>
- SEC EDGAR APIs:
  <https://www.sec.gov/search-filings/edgar-application-programming-interfaces>
- U.S. Treasury Fiscal Data API:
  <https://fiscaldata.treasury.gov/api-documentation/>
- Alpaca Market Data API:
  <https://docs.alpaca.markets/docs/about-market-data-api>
- Polygon market-data APIs:
  <https://polygon.io/docs>
- ORATS data APIs:
  <https://docs.orats.io/>
- Intrinio options data:
  <https://intrinio.com/options>
- Cboe DataShop / OPRA-category data:
  <https://datashop.cboe.com/>
- CFTC Commitments of Traders:
  <https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm>

These links are references for future due diligence, not repo-local integration
proof.

## 5. Recommended implementation sequence

The next DATA wave should be large enough to change product substance. Avoid
micro guards unless a task directly protects a new real-data integration.

| Next task | Scope | Dependencies | Conflict / serialization risk | Parallelization |
| --- | --- | --- | --- | --- |
| DATA-031 Official Risk Bundle Activation | Implement official VIX, Treasury/FRED rates, Fed liquidity readiness, persistence, and consumer-safe source snapshots. | Existing official macro contracts and cache-readiness runbooks. | Serial with any MarketCache/provider-runtime work; do not change provider order. | Can run in parallel with Options proof and Stock fundamentals design if no shared cache files are touched. |
| DATA-032 Authorized Quote Spine And Snapshot Store | Add durable quote/daily OHLCV snapshots for a bounded US/CN/HK acceptance universe with delay/freshness/source authority. | DATA-031 not strictly required, but quote authority rules must be aligned. | Serial for provider adapters, cache semantics, credential diagnostics, pricing provider order. | Can run after a read-only provider entitlement audit; should serialize implementation across markets if shared provider code changes. |
| DATA-033 Scanner Input Readiness And Candidate Evidence Packet | Persist universe, quote, history, profile, rejection, and blocker buckets; attach reusable candidate packet IDs. | DATA-032 for real quote/history; current scanner run/candidate tables. | Serial with scanner scoring/ranking changes; do not alter scoring thresholds unless explicitly scoped. | Can parallelize read-only universe/profile mapping with quote snapshot implementation; final integration serial. |
| DATA-034 Watchlist / Stock Research Packet Data Families | Expand row and symbol packets with durable quote/history refs, filings/news/events, fundamentals, peer/benchmark, and catalyst age. | DATA-032 quote spine; SEC plus FMP/Finnhub/Alpha-Vantage-like or official event source decisions. | Serial for shared packet schema/API contract and consumer-safe projection. | Fundamentals/event source normalization can be designed in parallel with Watchlist projection only if write scopes are separated. |
| DATA-035 Portfolio Valuation And Exposure Lineage | Add read-model lineage for position price source, FX freshness, benchmark/factor mapping, daily snapshots, and broker-sync provenance. | DATA-032 quote spine and FX source choice. | Must serialize with portfolio ledger/accounting changes; do not mutate ledger semantics. | Can parallelize read-only benchmark/factor mapping research with implementation of price/FX lineage. |
| DATA-036 Breadth, Flow, And Positioning Proof Bundle | Prove authorized breadth first, then flow and positioning source classes with freshness, rights, and coverage contracts. | DATA-031 and DATA-032 should be stable. | Serial for score-grade promotion; real flow licensing is manual-review heavy. | Breadth proof can run before flow; flow and positioning procurement/review can run in parallel as read-only tasks. |
| DATA-037 Options Chain Rights And Methodology Proof | Select or compare options provider class; attach entitlement, redistribution, decision-use, chain/IV/Greeks/OI/volume, freshness, coverage, and methodology proof. | None for docs/proof; implementation depends on vendor contract and source authority sign-off. | Must serialize with any Options Lab API/cache/runtime/frontend changes. | Can run in parallel with DATA-031/DATA-034 as a read-only/proof task; implementation later serial. |
| DATA-038 Scenario Baseline Snapshot Store | Persist scenario input snapshot IDs for market, portfolio, FX, macro, and cross-asset regime data; keep outputs deterministic from stored inputs. | DATA-031, DATA-032, DATA-035. | Serial with Scenario Lab API contract and portfolio read-model writes. | Starts after upstream snapshot contracts exist; not an early parallel implementation. |

Suggested sequence:

1. DATA-031 and DATA-037 can start together because official risk data and
   options proof do not need shared writes.
2. DATA-032 should begin once risk data authority vocabulary is settled.
3. DATA-033 and DATA-034 depend on DATA-032; DATA-034 can begin with schema
   design but should not claim readiness before quote/history refs exist.
4. DATA-035 depends on DATA-032 and should remain isolated from ledger writes.
5. DATA-036 should follow the quote/risk spine; breadth first, flow and
   positioning after manual rights review.
6. DATA-038 should be last because Scenario Lab needs stored upstream baseline
   inputs to become useful.

## 6. No-fake-data and no-advice constraints

Future integrations must preserve these constraints:

- No synthetic market facts: missing quote, history, fundamentals, filing,
  event, option-chain, IV, Greek, OI, volume, FX, breadth, flow, or positioning
  fields must stay missing, unavailable, not integrated, or observation-only.
- No fake provider success: credential presence, env variable names, cache hits,
  adapter construction, high coverage samples, or vendor labels cannot prove
  source authority.
- No fake freshness: delayed, cached, stale, partial, fallback, synthetic, or
  unknown data must not be projected as live or current.
- No hidden score promotion: source authority, score contribution,
  right-to-display, and consumer visibility are separate gates and must not be
  reused as aliases.
- No raw leakage: consumer packets and default routes should not expose provider
  payloads, raw diagnostics, credentials, request IDs, trace IDs, cache keys, or
  internal source-authority fields.
- No trading advice: integrations may produce research context, evidence gaps,
  risk states, and next data actions only. They must not output target prices,
  stop levels, position sizing, personalized action instructions, best-contract
  claims, broker/order language, or buy/sell/hold advice.
- No methodology shortcuts: gamma/GEX/vanna/charm/dealer-positioning outputs
  require provider rights proof, field coverage, sign assumptions, formula
  versions, stale handling, and consumer-safe labels before any UI/API adoption.

The existing packet contract captures the required posture: packets are
data-readiness objects, not provider integration plans or advice systems; missing
data must fail closed and no-advice copy must remain concise
(`docs/product-recovery/SYMBOL_RESEARCH_PACKET_CONTRACT.md:173`,
`docs/product-recovery/SYMBOL_RESEARCH_PACKET_CONTRACT.md:186`).

## 7. Private beta readiness view

Safe for a small private beta now:

- Home, Market Overview, Liquidity Monitor, Rotation Radar, Scanner, Watchlist,
  Stock Structure, Portfolio, Options Lab, Scenario Lab, and Research Radar can
  be shown as research surfaces when they use compact consumer-safe first reads,
  no-advice wording, and explicit data availability limits.
- Watchlist and Stock packet consumption is safe as an observation/readiness
  layer when missing families remain missing and provider internals stay hidden.
- Portfolio is safe for read-only account/holdings/ledger and research-state
  preview flows, provided valuation lineage and FX freshness are disclosed.
- Options Lab is safe as an observation lab only; current market-structure
  contracts are prerequisites, not production evidence.
- Scenario Lab is safe for bounded explanatory scenarios when it clearly shows
  input limits and does not imply execution readiness.

Must remain observation-only until real data is integrated:

- Scanner candidates generated from incomplete universe/quote/history/profile
  coverage.
- Rotation headline lanes that depend on fallback/static/taxonomy-only or
  proxy-only evidence.
- Market Overview / Liquidity score-grade conclusions when official VIX, rates,
  Fed liquidity, breadth, or flow sources are missing or stale.
- Watchlist/Stock fundamentals, filings, events, catalyst age, and peer/benchmark
  fields when no normalized source packet exists.
- Portfolio valuation, FX, factor exposure, and benchmark attribution when source
  lineage or snapshot freshness is absent.
- Options chain, IV, Greeks, OI, volume, GEX, gamma flip, vanna, charm, zero-DTE,
  and dealer-positioning outputs until entitlement, redistribution,
  decision-use, methodology, coverage, and freshness gates are approved.

Private beta should therefore position WolfyStock as a bounded research terminal:
useful for organizing observations, surfacing known evidence, showing gaps, and
guiding follow-up research. It should not be positioned as a trade execution
surface, a provider-authoritative terminal, or a decision-grade options/portfolio
engine until the roadmap data waves above land and pass review.
