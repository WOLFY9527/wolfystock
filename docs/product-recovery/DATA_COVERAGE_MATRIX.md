# WolfyStock Data Coverage Matrix

Task ID: DATA-001

This document is the repo-grounded data coverage matrix for WolfyStock product
recovery. It inventories what each surface needs, what the current code already
fetches or stores, what exists but is not productized, what is missing, candidate
providers, freshness/storage requirements, acceptance blockers, and the next
implementation sequence.

Authority rules used here:

- "Integrated" means a provider, adapter, endpoint, config key, or service path
  exists in this repository.
- "Candidate" means the provider may solve a gap, but repo code/config does not
  prove it is integrated.
- Public proxy, fallback, cached, mock, static, synthetic, taxonomy-only, stale,
  partial, unavailable, or unknown-source data does not become product-acceptance
  data unless the relevant source authority and freshness gates pass.
- No provider is assumed active from the presence of an environment variable
  alone.

## 1. Executive summary

WolfyStock's core issue is not route coverage. The codebase already has routes
for Market Overview, Decision Cockpit, Scanner, Watchlist, Stock Structure,
Research Radar, Portfolio, Scenario Lab, Liquidity Monitor, Rotation Radar, and
Options Lab shells or contracts. The product fails because the surfaces often
lack score-grade data, locally persisted snapshots, freshness metadata, source
authority, or a consumer-level packet that combines existing facts.

The P0 product blockers are:

1. Scanner cannot reliably produce useful candidates without a covered symbol
   universe, delayed/realtime quotes, daily history, profile metadata, and
   explicit empty-run blocker buckets.
2. Watchlist persists saved symbols and scanner lineage, but does not persist a
   row-level price, freshness, event, and research-status packet.
3. Stock Detail has quote, history, evidence, and structure endpoints, but the
   canonical Stock Structure page does not assemble a minimum useful research
   packet.
4. Market Overview and Decision Cockpit need official VIX, official rates/Fed
   liquidity, US index/ETF quotes, and breadth. Proxy/fallback rows remain
   observation-only or capped.
5. Options Lab lacks an authorized live options chain with IV, open interest,
   volume, Greeks, multiplier, entitlement, methodology, and redisplay rights.
6. Liquidity and Rotation have strong contracts, but their useful headline
   states require official or authorized VIX/rates/breadth/flow/ETF quote inputs.
7. Portfolio has account, trade, cash, broker-sync, FX, snapshot, and risk
   endpoints, but product acceptance depends on position lineage, price
   authority, FX freshness, benchmark mapping, factor mapping, and stored daily
   snapshots.

Highest-value source activation order:

1. Official VIX (`VIXCLS`) readiness and persistence.
2. Official Treasury/FRED rates and Fed liquidity cache readiness.
3. Alpaca US ETF/index quote readiness for Rotation Radar and Market Overview
   proxy ETFs, with credential/feed diagnostics only, not raw credentials.
4. Local quote and daily OHLCV snapshot persistence for a small acceptance
   universe across US/CN/HK.
5. Scanner universe and history readiness, then Watchlist and Stock research
   packets.

## 2. Current product data problem

The product has many endpoints, but the first user-visible answer frequently
depends on data that is missing, stale, fallback-only, or not persisted:

- Market Overview can fetch panels through `/api/v1/market-overview/*`, and the
  broader market endpoint module exposes crypto, sentiment, CN indices, breadth,
  flows, sector rotation, US breadth, rates, FX/commodities, decision cockpit,
  scenario lab, briefing, and futures routes. Its useful synthesis still fails
  closed when official volatility, macro, breadth, funds-flow, or quote evidence
  is unavailable.
- Scanner is a real backend workflow and persists runs/candidates in
  `market_scanner_runs` and `market_scanner_candidates`, but empty runs are valid
  terminal states when universe, quote snapshot, history, source gates, or local
  filters reject all candidates.
- Watchlist stores user-owned items in `user_watchlist_items`, including scanner
  lineage and score refresh fields. It does not store the live row facts a user
  expects: last price, change, quote timestamp, quote source, event freshness,
  and research packet state.
- Stock Structure has backend endpoints for quote, intraday, history, evidence,
  and structure decision. The page-level useful answer is still partial because
  quote/history/evidence are not assembled into one durable minimum packet.
- Research Radar is read-only aggregation over scanner and watchlist evidence.
  It cannot be useful until upstream Scanner and Watchlist data become useful.
- Options contracts and normalizers exist, but no repo path proves a live
  authorized options provider is enabled.
- Portfolio has durable accounting tables and broker-sync paths, but its user
  answer is blocked by market data authority and lineage, not by the lack of a
  route.

Data exists in code but is not fully surfaced:

- SEC EDGAR companyfacts parser/projection is parser-only and observation-only.
- Options chain normalization can represent chain fields, IV, OI, volume, and
  Greeks, but `liveProviderEnabled` is false in the normalizer contract.
- Official macro/VIX/Fed liquidity contracts and cache-readiness tooling exist,
  but activation still requires fresh official rows and bundle completeness.
- Polygon US breadth adapter exists, but it requires `POLYGON_API_KEY`, coverage
  thresholds, freshness checks, and licensing/authority review.
- Local US parquet helpers exist for daily history, but checked-in data is not a
  production dataset and the default parquet root is environment-dependent.
- Market persistence snapshot DTOs are inert/in-memory contracts, not a
  product-wide persisted market facts store.

## 3. Feature-by-feature matrix

| product surface | user-visible desired answer | required data fields | current source in code | current status | candidate source | freshness requirement | storage requirement | blocker severity | recommended task ID |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Market Overview | What is the market doing now, and which forces are driving risk? | index level/change, VIX, rates, USD/FX, commodities, breadth, funds/flow, sector rotation, freshness, source authority | `api/v1/endpoints/market_overview.py`; `api/v1/endpoints/market.py`; `src/services/market_overview_service.py`; `src/services/market_cache.py`; official macro contracts | partial | FRED/Treasury official rows; Alpaca ETF/index quotes; Polygon US breadth; authorized flow vendor | 30-180s for live panels, daily T+1 for official rates/VIX, weekly T+7 for Fed liquidity | MarketCache snapshot plus durable official macro/VIX/breadth snapshots keyed by panel/date/source | P0 | DATA-002 |
| Decision Cockpit / homepage | What should the user investigate first today? | Market Overview trust snapshot, top scanner candidates, watchlist queue, research packet status, catalyst age | `/api/v1/market/decision-cockpit`; `apps/dsa-web/src/api/marketDecisionCockpit.ts`; homepage services | surfaced poorly | Same as Market Overview plus Scanner/Watchlist packets | first screen under 1 minute for market state; scanner/watchlist packet within session/day | durable home briefing snapshot referencing market/scanner/watchlist evidence IDs | P0 | DATA-006 |
| Scanner | Which symbols are worth opening, and why did candidates pass or fail? | symbol universe, quote snapshot, daily OHLCV, volume/turnover, sector/theme profile, local filters, source confidence, blocker buckets | `api/v1/endpoints/scanner.py`; `src/services/market_scanner_service.py`; `src/repositories/scanner_repo.py`; `market_scanner_runs`; `market_scanner_candidates` | partial | Tushare/AkShare/Efinance for CN; Alpaca/Polygon/Tiingo/FMP/Nasdaq/Finnhub for US; Twelve Data for HK if entitlement passes | quote snapshot intraday or market delayed; daily history T+1; scanner run status immediate | persisted universe snapshots, quote snapshots, daily OHLCV windows, run blocker bucket, candidate evidence packet | P0 | DATA-005 |
| Watchlist | What changed in my saved symbols, and which need research now? | saved symbol, market, last price, change, quote timestamp/source, last scored at, research priority, catalyst age, latest scanner/evidence link | `api/v1/endpoints/watchlist.py`; `src/services/watchlist_service.py`; `src/services/watchlist_research_overlay_service.py`; `user_watchlist_items` | partial | Same quote/history providers as Scanner; scanner candidate store; news/filings/event providers | quote row 15m for open markets or latest close; research priority daily or on scanner run | `user_watchlist_items` plus quote/research packet table keyed by owner/symbol/as_of | P0 | DATA-006 |
| Stock Structure / Stock Detail | Is this symbol worth researching now, and what evidence supports it? | quote, daily/intraday history, volume, fundamentals, filings, news/catalyst, peer benchmark, sector/industry, scanner/watchlist context, data quality | `api/v1/endpoints/stocks.py` quote/intraday/history/evidence/structure-decision; `src/services/stock_service.py`; `src/services/single_stock_evidence_packet.py` | surfaced poorly | Existing fetchers plus SEC EDGAR live companyfacts, FMP/Finnhub/Alpha Vantage, provider-backed news/events | quote 15m/open-market or latest close; history T+1; filings/event same day; fundamentals after filing/report | persisted stock research packet with source refs, quote/history snapshot IDs, peer metadata | P0 | DATA-007 |
| Research Radar | What research queue items need attention, and what evidence is missing? | scanner candidates, watchlist items, evidence age, catalyst exposure, suggested research path, missing evidence bucket | `api/v1/endpoints/research.py`; `apps/dsa-web/src/api/researchRadar.ts`; watchlist research overlay | partial | Upstream Scanner/Watchlist/Stock packet sources | same session for queue; daily freshness for evidence age | read-only projection over persisted scanner/watchlist/stock packet rows | P1 | DATA-006 |
| Portfolio | What is my exposure, risk, and P&L with reliable prices and FX? | accounts, positions/lots, trades, cash ledger, corporate actions, broker sync state, price source, FX, sector/factor/benchmark mapping, daily snapshots | `api/v1/endpoints/portfolio.py`; `src/repositories/portfolio_repo.py`; `src/services/portfolio_service.py`; portfolio tables in `src/storage.py` | partial | Broker sync where configured; quote providers; official FX or authorized FX; benchmark/factor mapping vendor | positions/broker sync on demand or daily; quotes 15m/latest close; FX daily | durable portfolio snapshots, position lots, price lineage, FX rate cache, benchmark/factor mappings | P1 | DATA-008 |
| Options Lab | What does the chain imply, and which strikes/expiries have meaningful risk? | options chain, expiration, strike, side, bid/ask/last, volume, OI, IV, Greeks, multiplier, underlying spot, entitlement, delay, methodology | `src/services/options_chain_normalizer.py`; options authority contracts; frontend shell history | missing | Cboe/OPRA vendor, ORATS, Intrinio, Polygon Options, Tradier/Alpaca only after field/rights verification | live or explicitly delayed by entitlement; OI daily; IV/Greeks intraday or provider timestamped | chain snapshots by symbol/expiry/as_of plus rights/methodology metadata | P1 | DATA-011 |
| Scenario Lab | What happens to market/portfolio state under a bounded shock? | baseline regime, rates/VIX/USD/commodities/liquidity inputs, portfolio exposure, scenario assumptions, output provenance | `/api/v1/market/scenario-lab`; `apps/dsa-web/src/api/scenarioLab.ts`; portfolio scenario risk endpoint | partial | Official macro/VIX/rates plus Portfolio snapshot data | baseline daily or intraday depending scenario; scenario output deterministic from stored inputs | scenario run record with input snapshot IDs and output payload | P2 | DATA-010 |
| Liquidity Monitor | Is liquidity supportive, neutral, tight, or stressed, and why? | VIX, DXY/USD pressure, rates, credit stress, Fed liquidity, breadth, flows, ETF flow, crypto liquidity, evidence coverage | `apps/dsa-web/src/api/liquidityMonitor.ts`; liquidity docs/contracts; Market Overview inputs | partial | FRED/Treasury/VIXCLS; Polygon/authorized breadth; authorized ETF/fund flow; Binance/Coinbase for crypto | 30-180s for market proxies, daily T+1 official rows, weekly T+7 Fed liquidity | durable liquidity evidence snapshots by family and input with source authority fields | P1 | DATA-003 |
| Rotation Radar | Which sectors/themes are leading or fading with real quote evidence? | ETF/index quotes, intraday/daily OHLCV windows, theme membership, benchmark, breadth/correlation, source authority, taxonomy fallback flags | `/api/v1/market/rotation-radar`; `src/services/rotation_radar_quote_provider.py`; `apps/dsa-web/src/api/marketRotation.ts` | partial | Alpaca configured ETF quotes; Polygon/Tiingo/IEX category if authorized; official ETF issuer holdings for membership | 5m/15m/60m/1d windows; shared snapshot TTL around 180s | quote window snapshots, theme membership version, consumer evidence snapshot | P1 | DATA-004 |

## 4. Data-family coverage matrix

| data family | what product needs | current code already fetches/stores | current status | exists but not surfaced | totally missing or insufficient | provider candidates | freshness/SLA | local persistence needed | product blocker |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| symbol master / universe | canonical tradable symbols, names, market, exchange, active status, sector, listing status | CN/HK/US fetchers in `data_provider/base.py`; scanner universe/run tables; `apps/dsa-web/public/stocks.index.json` | partial | scanner universe notes and recent analysis symbols | authoritative US/HK universe and delisting/active flags | exchange listings, Polygon, Tiingo, Nasdaq Data Link, FMP, Finnhub, Tushare Pro, AkShare | daily | universe snapshot table by market/provider/date | P0 Scanner |
| real-time or delayed quote | last, change, pct, volume, timestamp, source, delay, authority | CN/HK/US quote paths via Efinance/AkShare/Tushare/Twelve Data/Alpaca/yfinance; stock quote endpoint | partial | quote endpoints not assembled into Watchlist/Stock packets | durable quote snapshots and authority metadata for all acceptance symbols | Alpaca, Polygon, Tiingo, IEX category, Twelve Data, Tushare/AkShare/Efinance | 15m or latest close with explicit delay | quote snapshot table keyed by symbol/as_of/source | P0 Watchlist/Stock/Scanner |
| daily OHLCV history | date, open/high/low/close, volume, adjusted fields, source | DataFetcherManager, yfinance, Alpaca, Twelve Data, CN fetchers; local US parquet helper | partial | local parquet helper can serve US history when configured | normalized daily store for acceptance universe | Polygon, Tiingo, Nasdaq Data Link, FMP, Twelve Data, Tushare, AkShare | T+1 trading day | daily bars partitioned by market/symbol/date/provider | P0 Scanner/Stock |
| intraday OHLCV | 1m/5m/15m/60m bars, timestamp, source, delay | stock intraday endpoint; Rotation Radar Alpaca windows and yfinance fallback | partial | Rotation window diagnostics | normalized intraday store and entitlement map | Alpaca, Polygon, Tiingo, Twelve Data, IEX category | 5-15m for consumer; provider timestamped | short-retention intraday bars by symbol/window | P1 Rotation/Stock |
| index quotes | SPX/DJI/NASDAQ/VIX/CN index/HK index/ETF proxy quotes | Market Overview index panels; US index yfinance path; CN/HK routes | partial | US ETF quote activation docs | official/authorized US index/ETF quote source | Alpaca ETF quotes, Polygon, Tiingo, official index vendors | 30s-15m explicit delay | index/ETF quote snapshot table | P0 Market Overview |
| sector / industry mapping | sector, industry, theme, board membership, mappings to ETFs | CN board/sector data; scanner profiles; Rotation taxonomy | partial | taxonomy themes used but quarantined from headline lanes | authoritative US/HK sector/industry and theme membership | GICS/FactSet/Refinitiv category, FMP/Finnhub, official exchange/issuer data | weekly/monthly plus change events | versioned symbol-sector and theme membership table | P1 Rotation/Stock |
| ETF / index membership | constituent symbols, weights, effective date, source | Rotation theme registry/proxies; not official membership | missing | ETF proxy summary can show proxy evidence | official membership/weights for ETF/index-backed analysis | ETF issuer holdings, official index provider, Polygon/FMP/Tiingo/Nasdaq Data Link candidates | daily for ETF holdings, scheduled for index changes | membership snapshot by provider/effective date | P1 Rotation/Portfolio |
| breadth | advancers/decliners/unchanged, new highs/lows, A/D ratios | CN breadth endpoints/cache; US breadth contracts; Polygon US breadth adapter | partial | Polygon adapter can compute if configured and coverage passes | authorized US broad-market breadth feed | Polygon with key/coverage; official/authorized breadth vendor | same session or EOD T+1 | breadth snapshot by market/date/session | P0 Market Overview |
| volume / turnover | traded value, turnover, relative volume, liquidity screens | quote/OHLCV providers and scanner key metrics | partial | scanner candidates store key metrics JSON | durable normalized turnover across markets | same as quote/OHLCV providers | quote/intraday or T+1 | quote/bar snapshots with turnover fields | P0 Scanner |
| macro rates | Treasury yields, policy rates, credit stress, SOFR/DFF, Fed liquidity | official macro transport/cache contracts; FRED/Treasury docs and fixtures | partial | readiness diagnostics and prewarm scripts | complete live/prewarmed official rows for product surfaces | FRED, Treasury, NY Fed/official sources | daily T+1 for rates, weekly T+7 for Fed liquidity | official macro series store by series/date/source | P0 Market Overview/Liquidity |
| VIX / volatility | VIX close/live proxy, source, freshness, authority | Market Overview volatility; official macro source registry; `VIXCLS` docs | partial | official VIX contract exists | fresh official VIX row in cache/store | FRED `VIXCLS`; Cboe official candidate if verified | daily T+1, max policy from contract | VIX series store by date/source | P0 Market Overview/Liquidity |
| FX / commodities | USD/DXY, major FX, gold/oil/commodities, source, delay | FX/commodities market endpoints and contracts; portfolio FX cache | partial | portfolio FX cache exposed separately | official/authorized DXY/commodity source and FX lineage | FRED/Treasury where official, Twelve Data/Polygon/Tiingo/Alpha Vantage candidates | 30-60s for market proxy or daily official | FX/commodity snapshot table | P1 Market/Portfolio |
| crypto | BTC/ETH/crypto liquidity, quotes, freshness | market crypto endpoint; Binance/Coinbase-related providers in repo | partial | crypto can feed liquidity as evidence | authority/freshness classification across exchanges | Binance public, Coinbase public; paid institutional crypto feeds if needed | seconds to 15s for live panels | crypto quote snapshot short retention | P2 Liquidity |
| fundamentals | valuation, profitability, growth, ratios, source, period | CN fundamental adapter; US fundamentals provider using FMP/Finnhub/Alpha Vantage/Yahoo-style sources | partial | snapshots can be stored through storage methods | normalized cross-market fundamental packet with period/source | FMP, Finnhub, Alpha Vantage, SEC company facts, Tushare/AkShare | quarterly/after filing; daily cache | fundamental snapshot by symbol/period/provider | P1 Stock |
| financial statements | income, balance sheet, cash flow, period, restatement/source | US FMP/Alpha Vantage functions; CN AkShare/Tushare-style adapters | partial | statement-derived metrics in pipeline | complete statement history and source mapping | FMP, Alpha Vantage, SEC EDGAR companyfacts, Tushare Pro, AkShare | after filing/report; daily refresh for new filings | financial statement normalized tables | P1 Stock |
| SEC filing / company facts | companyfacts, filing metadata, facts, refs, official source tier | `data_provider/sec_edgar_provider.py` parser-only; SEC evidence sidecars | partial | parser/projection not live-fetched | live SEC companyfacts fetcher and accession/filing refs | SEC EDGAR official public | filing/day-of update | SEC companyfacts cache by CIK/as_of | P1 Stock |
| CN filings / announcements | announcements, earnings warnings, regulatory notices, source/date | AkShare fundamental adapter references announcement fields; agent/news prompts search announcements | partial | extracted fields may feed reports | official exchange disclosure feed and normalized announcement store | SSE/SZSE/HKEX official feeds, Tushare/AkShare candidates | same day | announcement/event table by symbol/date/source | P1 Research/Stock |
| earnings calendar | date, expected/actual EPS/revenue, report time, source | event/option calendar authority contracts and limited homepage copy; no proven product calendar | missing | event intelligence contracts can represent event types | verified earnings calendar feed | Finnhub, FMP, Nasdaq candidate, exchange/company IR feeds | daily, intraday around earnings | event calendar table by symbol/event/date/source | P1 Research/Stock/Options |
| news / event catalyst | headline, source, timestamp, event type, refs, freshness | Tavily/SerpAPI/GNews/newspaper config; agent/news services; report renderer | partial | latest news appears in reports, not core stock packet | durable event/catalyst store with citation and stale handling | Finnhub/FMP/news APIs, GNews, Tavily, SerpAPI, official filings | intraday for news; same day for events | event/catalyst table with refs and source quality | P1 Research/Watchlist |
| peer group / benchmark | peer symbols, benchmark index/ETF, correlation, sector/industry | Stock peer logic requires local metadata/history; scanner profiles include benchmarks | partial | peer insufficient states are explicit | verified peer mappings and benchmark history | FMP/Finnhub/Polygon/Tiingo/official index/ETF data | daily/weekly | peer group and benchmark mapping version table | P1 Stock/Portfolio |
| options chain | contracts by expiration/strike/side, quotes, bid/ask/last | options chain normalizer and frontend shell/contracts | missing | normalizer can parse caller-supplied data | live authorized options chain | Cboe/OPRA vendor, ORATS, Intrinio, Polygon Options, Tradier/Alpaca only after verification | provider timestamped, live or explicitly delayed | option chain snapshot store | P1 Options |
| IV / OI / volume / Greeks | IV, OI, contract volume, delta/gamma/vega/theta/rho, multiplier | normalizer fields and gamma methodology prerequisites | missing | contracts can carry fields if supplied | authorized data plus methodology and entitlement proof | ORATS, Cboe/OPRA vendor, Intrinio, Polygon Options, Tradier/Alpaca after verification | IV/Greeks intraday; OI daily | chain analytics snapshot by contract/as_of | P1 Options |
| GEX / vanna / charm prerequisites | chain, OI, gamma, spot, multiplier, maturity, IV surface, methodology | GEX prerequisite/methodology contracts only | missing | GEX observation adapter exists but not product-grade live input | complete options dataset and audited calculation methodology | ORATS/Cboe/OPRA/Intrinio category | intraday plus OI daily | derived exposure snapshots with input IDs | P2, do not build yet |
| portfolio position / broker data | accounts, positions/lots, trades, cash, corporate actions, broker sync state | Portfolio tables/endpoints, broker connection and IBKR sync services | partial | snapshot diagnostics expose gaps | reliable broker ingestion plus pricing/FX authority | broker APIs, IBKR sync, CSV import, market quote providers, FX provider | on demand/daily | portfolio ledger, lots, broker sync, daily snapshots | P1 Portfolio |

## 5. Provider inventory currently in repo

| provider/source | repo proof | integrated status | key/paid status | data families | authority notes |
| --- | --- | --- | --- | --- | --- |
| Existing local SQLite | `DATABASE_PATH=./data/stock_analysis.db`; `src/storage.py` SQLAlchemy models | integrated runtime storage | local | scanner runs/candidates, watchlist, portfolio, snapshots, fundamentals | storage exists, not a market-data authority |
| Existing local US parquet | `src/services/us_history_helper.py` reads `LOCAL_US_PARQUET_DIR` or `US_STOCK_PARQUET_DIR` | integrated helper | local operator data | US daily OHLCV | helper exists; no production parquet data is checked in as authoritative |
| Existing frontend symbol index | `apps/dsa-web/public/stocks.index.json` | integrated static asset | local | symbol search | useful for UI search, not a canonical universe |
| MarketCache | `src/services/market_cache.py` TTL/SWR cache with optional remote mirror protocol | integrated cache | local | market panels | cache status can be fresh/stale/fallback; cache is not authority by itself |
| Efinance | `data_provider/efinance_fetcher.py`; DataFetcherManager priority | integrated adapter | public/unknown stability | CN quotes/history/boards | public web interface, not official authority |
| AkShare | `requirements.txt`; `data_provider/akshare_fetcher.py`; fundamental adapter | integrated adapter | public/unknown stability | CN/HK quotes/history/fundamentals/announcements/boards | public aggregation, source authority must be explicit per use |
| Tushare Pro | `TUSHARE_TOKEN`; `data_provider/tushare_fetcher.py` | integrated adapter | key-required, plan/points likely | CN universe/quotes/history/fundamentals | can be stronger than scraping, but token/entitlement and field coverage must pass |
| Pytdx | `data_provider/pytdx_fetcher.py` | integrated adapter | public/server-dependent | CN market data | operational reliability and authority unknown |
| Baostock | `data_provider/baostock_fetcher.py` | integrated adapter | public/account-free category | CN historical data | useful fallback, not enough for realtime |
| yfinance | `requirements.txt`; `data_provider/yfinance_fetcher.py`; US index fallback path | integrated adapter | public proxy | US/HK quotes/history/index proxies/fundamentals fallback | treated as fallback/proxy; not score-grade authority where official/authorized source is required |
| Alpaca | `ALPACA_API_KEY_ID`; `ALPACA_API_SECRET_KEY`; `ALPACA_DATA_FEED`; `data_provider/alpaca_fetcher.py`; Rotation quote provider | integrated adapter/config | key-required; feed entitlement required; paid/plan unknown | US stock quotes/history, ETF quote windows, possible options category only if verified | source can qualify only after credential/feed/freshness/coverage/rights proof |
| Twelve Data | `TWELVE_DATA_API_KEY(S)`; `data_provider/twelve_data_fetcher.py` | integrated adapter/config | key-required, paid/plan unknown | HK/US quote/history fallback | entitlement and delay must be verified |
| Polygon | `POLYGON_API_KEY`; `src/services/polygon_us_breadth_provider.py` | integrated for US breadth adapter | key-required, paid/plan likely for production | computed US breadth from grouped daily rows | code labels authorized feed, but product use still requires key, coverage, freshness, and license review |
| FRED | `FRED_API_KEY`; official macro transport/source registry | integrated official macro path | optional key depending endpoint/rate | VIXCLS, rates, macro, credit stress | official-public source, but row freshness and bundle completeness still gate scoring |
| Treasury / official macro sources | official macro transport/source registry | integrated official macro path | public/official | Treasury rates and official macro rows | official authority if source metadata and freshness pass |
| Finnhub | `FINNHUB_API_KEY(S)`; `data_provider/us_fundamentals_provider.py` | integrated adapter/config | key-required; paid/plan unknown | US quote/metrics/fundamentals/news category | coverage/rights unknown until verified |
| Financial Modeling Prep (FMP) | `FMP_API_KEY(S)`; `data_provider/us_fundamentals_provider.py` | integrated adapter/config | key-required; paid/plan unknown | US fundamentals/statements/historical data | useful fundamentals candidate, verify license and point-in-time fields |
| Alpha Vantage | `ALPHA_VANTAGE_API_KEY`; `data_provider/alphavantage_provider.py` | integrated adapter/config | key-required; free/paid tiers | company overview, income statement, technical indicators | rate limits and statement coverage must be verified |
| SEC EDGAR companyfacts | `data_provider/sec_edgar_provider.py`; SEC evidence services | parser/projection integrated, live fetch not proven | official public | SEC companyfacts/filing metadata | parser-only for already loaded payloads; observation-only unless a live official fetch/cache task is added |
| Binance / Coinbase public crypto | crypto services/providers in repo | integrated category | public/unknown limits | crypto quotes/liquidity | can support crypto panel when freshness/source metadata pass |
| Tavily / SerpAPI / GNews / newspaper | env keys and agent/news/report paths | integrated search/news category | keys for APIs; public extraction for newspaper | news/events/catalysts | news requires citation/freshness and should not become market-data authority |
| CN/HK Connect flow cache | provider-data docs and cache path config | cache-only diagnostic path | local cache; provider unknown | CN/HK flows | observation-only unless provider authority is separately proven |
| CN money-market rates cache | provider-data docs and cache path config | cache-only diagnostic path | local cache; provider unknown | CN rates/money market | observation-only/readiness diagnostic path |
| Nasdaq Data Link | provider operations matrix/env-key mapping only | not integrated as data adapter | key-required; paid/unknown | candidate macro/reference/fundamentals | no repo-local adapter proves use |

## 6. Provider candidates not yet integrated

| provider candidate | candidate for | integration status | likely access/rights state | recommendation |
| --- | --- | --- | --- | --- |
| Tiingo | US quotes/history/reference/news | not found as adapter/config in repo | key-required; paid/unknown | evaluate only after core Alpaca/official macro/Scanner persistence tasks |
| ORATS | options chain, IV, Greeks, OI, history | not integrated | paid/key-required; options license required | use for Options Lab proof-of-data task, not direct UI launch |
| Intrinio | options, fundamentals, market data | not integrated | paid/key-required; license required | compare with ORATS/Cboe/Polygon Options before implementation |
| Cboe DataShop / OPRA vendor category | options quotes, historical chains, IV/OI/Greeks via licensed source | not integrated; docs mention only as candidate/authority requirement | paid/license-heavy | required category for production-grade Options Lab; procurement/license task first |
| Tradier | options chain pilot | not integrated | key/account required; OPRA/ORATS details must be verified | possible narrow pilot if fields/rights meet Options Lab contract |
| Official index providers / ETF issuer holdings | index/ETF membership and weights | not integrated | paid or public issuer files depending source | needed before Rotation/Portfolio treat ETF/index membership as authority |
| Official exchange filings feeds (SSE/SZSE/HKEX/Nasdaq/NYSE/issuer IR) | filings, announcements, earnings dates | not integrated as normalized feed | public/paid mixed; source authority must be checked | add only through event/filing packet task |
| Official or authorized breadth vendor | US/CN/HK market breadth | Polygon partial path exists for US breadth, broader official source not integrated | paid/unknown | use only if Polygon cannot satisfy coverage/license needs |
| SEC EDGAR live companyfacts fetcher | US company facts and filing metadata | parser exists; live fetch/cache not integrated | official public, rate-policy sensitive | implement as official-public cache with user-agent/runbook |

## 7. Market Overview data gaps

Market Overview needs a small number of authoritative series more than it needs
new UI:

- Official VIX: `VIXCLS` must be present, fresh, and source-authorized. yfinance
  or other proxy volatility stays capped.
- Official rates and Fed liquidity: Treasury/FRED daily rows and weekly Fed
  liquidity rows must pass completeness and freshness separately.
- US breadth: the Polygon grouped-daily adapter can compute breadth only with a
  key, enough rows, recent dates, and license/authority review.
- US index/ETF quotes: current shared US index routing uses yfinance for indices;
  Rotation Radar has Alpaca-first ETF windows. Market Overview needs an
  authorized quote path for ETF/index proxies before score-grade synthesis.
- Funds flow: CN/HK Connect flow is cache-only and observation-only in current
  docs; real funds/ETF flow should remain deferred until provider authority is
  verified.

Required next task: DATA-002 for VIX plus DATA-003 for macro/rates/Fed liquidity,
then DATA-004 for US ETF/index quote authority.

## 8. Scanner data gaps

Scanner usefulness is blocked by input readiness, not the absence of a backend
job. The repo persists `MarketScannerRun` metadata and `MarketScannerCandidate`
rows, including summary, diagnostics, universe notes, scoring notes, reasons,
metrics, feature signals, risk notes, watch context, boards, and diagnostics.

Missing or insufficient:

- covered symbol universe by market/profile;
- quote snapshot with source/freshness/authority;
- daily OHLCV history window for each candidate;
- volume/turnover and relative liquidity metrics;
- sector/theme/profile metadata;
- local filter rejection counts and user-facing blocker bucket;
- candidate evidence packet that Watchlist and Research Radar can reuse.

Required next task: DATA-005. It should persist scanner input readiness and
blocker buckets before adding more scoring.

## 9. Watchlist data gaps

Watchlist currently stores the user's saved item and scanner lineage:
`symbol`, `market`, `name`, `source`, `scanner_run_id`, `scanner_rank`,
`scanner_score`, `last_scored_at`, `score_source`, `score_profile`,
`score_reason`, `score_status`, `score_error`, `theme_id`, and `universe_type`.

Missing for product acceptance:

- last price, change, percent change, volume, quote timestamp, quote source;
- quote freshness/delay/source authority fields;
- latest scanner candidate evidence link;
- latest Stock research packet status;
- event/catalyst age and filing/news refs;
- explicit "needs refresh", "needs evidence", and "ready to research" states.

Required next task: DATA-006. It should add a row-level Watchlist data packet,
not another disclaimer or empty-state copy pass.

## 10. Stock detail data gaps

The backend has the ingredients for a useful stock page:

- validation/search-style stock endpoints;
- quote endpoint;
- intraday endpoint;
- daily history endpoint;
- evidence endpoint;
- structure-decision endpoint;
- single-stock evidence packet helpers.

The gap is product assembly and persistence:

- quote/history/evidence are not merged into a single page-level packet;
- SEC companyfacts are parser/projection only, not live-cached official data;
- filings and catalyst evidence can be observation-only or absent;
- peer groups require local metadata and local OHLCV before they are useful;
- US/HK fundamentals and statement data are provider-fragmented;
- CN announcements exist as adapter fields, not a normalized event store.

Required next task: DATA-007. Build a minimum research packet with quote,
history, source refs, filings/news/fundamentals when available, and explicit
missing evidence buckets.

## 11. Research Radar data gaps

Research Radar should not become a standalone data source. It should project the
work queue from Scanner, Watchlist, and Stock packets.

Current gap:

- if Scanner has no useful candidates, Research Radar has no useful queue;
- if Watchlist rows lack price/freshness/catalyst state, Research Radar can only
  explain missing evidence;
- if Stock packets do not persist filings/news/fundamentals refs, Research Radar
  cannot rank research priority.

Required next task: finish DATA-005, DATA-006, and DATA-007 first. Research Radar
should then become a read-only consumer of those packet IDs.

## 12. Options Lab data gaps

Options Lab is not blocked by calculations first. It is blocked by source data
and rights:

- no proven live options provider adapter is enabled;
- chain fields must include expiration, strike, side, bid, ask, last, volume,
  open interest, IV, Greeks, multiplier, underlying spot, provider timestamp,
  entitlement, and delay;
- GEX needs chain, OI, gamma, multiplier, spot, expiry, and methodology proof;
- vanna/charm need IV surface and sensitivity methodology beyond basic chain
  fields;
- OPRA/exchange/vendor display and derived-data rights must be verified before
  public product use.

The current normalizer/contracts are useful as acceptance contracts, not as
evidence that options data is integrated.

Required next task: DATA-011 should be a provider proof and rights/methodology
task only. Do not build GEX/vanna/charm product features yet.

## 13. Portfolio / Scenario / Liquidity / Rotation data gaps

Portfolio:

- Existing tables cover accounts, broker connections, broker sync state,
  broker sync positions/cash, trades, cash ledger, corporate actions, positions,
  lots, daily snapshots, and FX rates.
- Existing endpoints cover account CRUD, broker connection CRUD, IBKR sync,
  trades, cash, corporate actions, snapshot, structure review, history, imports,
  FX refresh, scenario risk, and risk report.
- Product acceptance still needs position price lineage, FX freshness,
  benchmark/factor mapping, corporate-action handling quality, broker sync
  provenance, and snapshot freshness invalidation.

Scenario Lab:

- Scenario output should reference stored market/portfolio input snapshots.
- Without official VIX/rates/liquidity and Portfolio snapshot authority, Scenario
  Lab should stay bounded and explanatory.

Liquidity Monitor:

- Needs official VIX/rates/Fed liquidity first.
- ETF/fund flow and CN/HK flow should remain observation-only unless source
  authority is proven.
- Crypto can contribute when fresh, but it cannot substitute for official macro
  liquidity.

Rotation Radar:

- US theme headlines require real quote coverage and source authority.
- Alpaca-first ETF windows exist, with yfinance fallback, but fallback/static or
  taxonomy-only evidence cannot populate headline lanes.
- Official ETF/index membership and weights are still missing.

Required next tasks: DATA-003, DATA-004, DATA-008, and DATA-010.

## 14. Local storage / cache / freshness inventory

| storage/cache path | current role | data retained | freshness behavior | gap |
| --- | --- | --- | --- | --- |
| `./data/stock_analysis.db` via `DATABASE_PATH` | primary SQLite runtime store | users, scanner, watchlist, portfolio, snapshots, analysis/fundamentals tables | application-defined | not a normalized market facts store |
| `market_scanner_runs` | scanner run metadata | market/profile/universe/status/counts/timestamps/diagnostics | run timestamp/completed timestamp | needs explicit blocker bucket and input readiness packet |
| `market_scanner_candidates` | scanner shortlist rows | symbol/rank/score/reasons/metrics/signals/watch context | candidate creation timestamp | depends on upstream quote/history/source readiness |
| `user_watchlist_items` | saved symbols and scanner score lineage | symbol/market/name/source/scanner fields/score fields/theme | `updated_at`, `last_scored_at` | no quote/freshness/event/research packet |
| Portfolio tables | accounting and broker/snapshot store | accounts, trades, cash, corporate actions, lots, broker sync state, FX, daily snapshots | snapshot date, rate date, sync timestamps | market-price authority and FX freshness still gate usefulness |
| `MarketCache` | in-memory market panel cache with TTL/SWR | market panel payloads | TTLs: crypto 15s, futures/index 30s, FX 60s, breadth 60s, flows/rotation 180s, sentiment 1800s, rates 600s | cache freshness is not source authority; persistent mirror is optional |
| official macro cache contracts | readiness and prewarm path for official rows | VIX/rates/Fed liquidity cache bundles | daily T+1 and weekly T+7 policies | activation/completeness proof still required |
| local US parquet helper | optional local US daily history | per-symbol parquet daily bars | depends on file contents | no checked-in production dataset; default root is environment-dependent |
| `apps/dsa-web/public/stocks.index.json` | frontend search index | symbol/name lookup | static asset | not canonical product universe |
| market persistence snapshot DTO | inert append-only/in-memory contract | evidence snapshots with source/freshness/authority fields | caller-supplied timestamps | not wired to DB/cache/provider runtime |

## 15. Data source priority list

1. Official VIX (`VIXCLS`) for Market Overview and Liquidity.
2. Official rates and Fed liquidity bundle through FRED/Treasury/official
   sources.
3. Alpaca US ETF/index quote activation for stable ETF probes and Rotation Radar.
4. Local quote and daily OHLCV persistence for a small acceptance universe.
5. Scanner universe/profile/history readiness persistence.
6. Watchlist row data packet backed by quote/scanner/research refs.
7. Stock minimum research packet backed by quote/history/evidence refs.
8. Polygon or other authorized US breadth proof.
9. Fundamentals/filings/events packet, starting with SEC EDGAR live cache for US
   and normalized CN announcement evidence.
10. Options chain provider proof, rights review, and methodology acceptance.

## 16. Next 10 implementation tasks ranked by product value

| rank | task ID | task | product value | acceptance output |
| --- | --- | --- | --- | --- |
| 1 | DATA-002 | Official VIX readiness and storage | unlocks Market Overview/Liquidity risk state | fresh `VIXCLS` row with source authority, cache/store proof, and tests |
| 2 | DATA-003 | Official macro/rates/Fed liquidity bundle | unlocks market regime and liquidity interpretation | Treasury/FRED/Fed rows with freshness policies and complete bundle state |
| 3 | DATA-004 | Alpaca ETF/index quote authority proof | unlocks Rotation Radar and US market proxy quote spine | sanitized credential/feed diagnostics plus stable ETF probe evidence |
| 4 | DATA-005 | Scanner universe/history/quote readiness | turns Scanner from empty terminal states into actionable candidates | persisted input readiness, blocker buckets, and candidate evidence packet |
| 5 | DATA-006 | Watchlist row data packet | makes saved symbols useful | quote/freshness/research/catalyst state per watchlist row |
| 6 | DATA-007 | Stock minimum research packet | makes Stock Detail useful | durable packet combining quote, history, evidence, filings/news/fundamentals refs |
| 7 | DATA-008 | Portfolio price/FX lineage packet | makes Portfolio risk and P&L credible | price source, FX freshness, benchmark/factor mapping, snapshot invalidation |
| 8 | DATA-009 | US breadth provider proof | improves Market Overview and Liquidity breadth signals | Polygon or other authorized breadth coverage/freshness/license proof |
| 9 | DATA-010 | Fundamentals/filings/events packet | improves Stock/Research Radar/Watchlist catalyst quality | SEC companyfacts cache plus normalized events with source refs |
| 10 | DATA-011 | Options provider rights and methodology proof | prepares Options Lab without premature analytics | chain sample with IV/OI/Greeks/multiplier plus entitlement/redisplay/methodology review |

## 17. What not to build yet

- Do not build GEX, vanna, charm, or options strategy ranking until authorized
  options chain data and methodology are proven.
- Do not add more disclaimers, badges, fallback copy, or diagnostic panels as a
  substitute for data.
- Do not relax existing source authority gates to make proxy or stale data look
  useful.
- Do not treat provider names, cache presence, or freshness alone as authority.
- Do not build real funds-flow scoring until a licensed/authorized source is
  selected and verified.
- Do not expand broker execution, portfolio rebalancing, or order workflows as
  part of data recovery.
- Do not add broad provider runtime refactors before the P0 source activation
  tasks prove useful data.
- Do not let Research Radar invent priority from missing upstream evidence.
- Do not ship static/demo/fallback scanner candidates as product answers.
- Do not make UI redesign the next task; the missing data packets are the next
  task.

## 18. Validation performed

Read-only discovery covered the required directories and documents:

- Required product recovery and Codex policy docs under `docs/product-recovery`
  and `docs/codex`.
- Endpoint inventory under `api/v1/endpoints`.
- Service/provider inventory under `src/services`, `data_provider`, and
  provider-related config.
- Frontend API/page surface inventory under `apps/dsa-web/src/api` and
  `apps/dsa-web/src/pages`.
- Data/provider docs under `docs/data`, `docs/provider-data`,
  `docs/data-reliability`, `docs/liquidity`, and `docs/rotation`.
- Config/provider names in `.env.example`, `requirements.txt`, and service
  source files.

Delivery validation is performed by the worker before commit and recorded in the
final report:

- `git diff --check origin/main...HEAD`
- `git diff --check`
- `bash scripts/release_secret_scan.sh --base-ref origin/main`

This task intentionally made no runtime code, backend API, provider adapter,
cache schema, database migration, or frontend UI changes.
