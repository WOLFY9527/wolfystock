# Market Data Provider Upgrade Decision Matrix

Date: 2026-05-07
Mode: docs-only decision matrix. No runtime provider behavior, provider ordering, fallback behavior, credentials, config defaults, API keys, tests, frontend, Options Lab, Data Pipeline, MarketCache, quota enforcement, or provider circuit enforcement were changed.

## 1. Executive summary

Free and unofficial providers remain useful for local development, demos, fallback paths, and low-confidence enrichment, but they are not sufficient as the primary source for decision-grade analysis. Data Pipeline R1 reduces perceived slowness by separating fast decision output from progressive enrichment, but it does not solve missing fundamentals, incomplete news attribution, option-chain gaps, stale data, or licensing uncertainty.

Recommended short-term stack:

| Layer | Recommendation | Why |
| --- | --- | --- |
| Free/fallback stack | Keep existing local-first/free-source posture with yfinance/Yahoo-style data treated as research fallback only. | Preserves current no-cost behavior and development ergonomics while preventing unofficial data from being labeled decision-grade. |
| Paid pilot stack | Pilot Polygon for US equities quotes/candles/reference/news and FMP for fundamentals; keep Alpaca as an alternate US quote/candle pilot where brokerage-aligned access is useful. | Polygon gives a broad market-data surface with clear US equities/options paths; FMP is strongest as a fundamentals-first complement; Alpaca is simple for authenticated quote/candle enrichment but less complete as a fundamentals/news system. |
| Options-specific stack | Pilot Tradier for low-friction option chains with Greeks, then evaluate Polygon Options or ORATS/Cboe-style vendors for production-grade IV/OI/Greeks/history. | Options Decision Engine usefulness depends on chain completeness, bid/ask quality, IV, Greeks, open interest, and history. Tradier is a practical first adapter; ORATS/Cboe/OPRA-category vendors are the stronger decision-grade options-data path. |
| Macro/rates | Keep public official sources where possible, then evaluate Twelve Data or Alpha Vantage only as normalized API convenience layers. | Macro data is often available from official/public sources; paid wrappers help latency and normalization but add license and quota review. |
| China/HK | Keep current local-first/free-source fallback; evaluate Twelve Data for HK quote/history enrichment and a dedicated licensed China/HK vendor before treating data as decision-grade. | China/HK data licensing and exchange coverage differ materially from US equities; do not infer US-provider quality applies there. |

Near-term priority should be **data quality tiering and disabled-by-default paid adapters**, not a provider-order cutover. Any pilot should run through provider circuit dry-run/observability first, disclose cache/freshness, and avoid changing live provider ordering until field completeness and license posture are proven.

## 2. Decision criteria

| Dimension | Decision-grade expectation | Reject or fallback condition |
| --- | --- | --- |
| Latency | Fast enough for current route family without walking deep fallback chains; stable p95 under expected concurrency. | High timeout rate, burst throttling, or route-level stalls that hide behind progressive enrichment. |
| Field coverage | Explicit support for required quote, candle, reference, fundamentals, news, macro, or option fields. | Missing key fields such as financial statements, bid/ask, open interest, IV, Greeks, corporate actions, or source timestamps. |
| Options Greeks | Native or vendor-calculated delta/gamma/theta/vega, IV, OI, and bid/ask with clear calculation/source semantics. | Greeks only in UI, unavailable through API, delayed without disclosure, or computed from incomplete inputs. |
| Rate limits | Published limits and commercially viable quota for expected route volume. | Unknown limits, low free-tier request caps, punitive burst behavior, or no clean 429 handling. |
| Historical depth | Enough history for trend, backtest, IV rank/percentile, fundamentals comparison, and audit replay. | Short lookback, no point-in-time fundamentals, no option-chain history, or inconsistent split/corporate-action treatment. |
| Pricing/cost | Cost scales predictably with users, routes, symbols, and refresh cadence. | Per-user/display/non-display fees or OPRA/exchange fees not understood before product exposure. |
| License/redistribution risk | Terms support the intended internal, user-visible, and cached usage. | Personal-use-only, unofficial scraping, unclear redistribution rights, or broker-only entitlement mismatch. |
| API stability | Versioned docs, SDKs, status page or changelog, stable schemas, and structured errors. | Scraped/unstable endpoints, unversioned payloads, frequent field drift, or weak error contracts. |
| Credential/security burden | Supports standard secret handling, bounded scopes, rotation, and no raw provider payload logging. | Broad broker credentials, session-gateway dependency, raw query leaks, or entitlement errors that encourage repeated probing. |
| Fit for decision-grade analysis | Strong enough to support conservative AI/rule decisions with source, freshness, and confidence disclosure. | Good for charts but not for recommendations, options suitability, fundamentals reasoning, or audit evidence. |

## 3. Provider category fit

| Provider/category | US equities quote/candles | Fundamentals | News/sentiment | Options chain/Greeks/IV/OI | Macro/rates | China/HK | Decision-grade fit |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Alpaca | Strong for authenticated US market data; paid plans add broader market coverage beyond free IEX/indicative feeds. | Limited relative to fundamentals-first vendors. | Not primary. | Useful for option market data on paid OPRA-backed plan, but verify chain/Greek fields against Options Engine needs. | Not primary. | Not primary. | Good quote/candle pilot; not a complete research stack alone. |
| Polygon | Strong US equities API, historical depth, real-time paid tiers, reference/corporate actions. | Good and improving; verify point-in-time fields and ratios needed by reports. | Good API surface for stock news/sentiment-style metadata. | Strong candidate: options docs emphasize OPRA-sourced coverage, IV, Greeks, OI, historical/tick data. | Limited versus macro specialists. | Not primary. | Best broad US market-data pilot if license/cost is acceptable. |
| Tradier | Adequate for brokerage-oriented quote access. | Not primary. | Not primary. | Practical low-friction options chain endpoint; Greeks and IV are included when requested and documented as ORATS-backed. | Not primary. | Not primary. | Best first options adapter pilot because integration surface is narrow. |
| IBKR | Strong broker-linked market data if subscriptions and API entitlements are correct. | Broker/research subscriptions may exist, but not clean as an app-wide data vendor. | Not primary. | Can return option Greeks via TWS API market-data requests when option and underlying subscriptions exist. | Broker subscriptions vary. | Broad global market access but subscription-specific. | Useful for user-owned broker overlay; poor fit as default shared app provider due to sessions, entitlements, and API-gateway burden. |
| FMP | Good enough for many quote/history use cases, but not the primary low-latency feed. | Strong candidate for financial statements, ratios, company profiles, analyst-style fields. | Has market/news endpoints, but validate source coverage and license. | Not primary. | Some economic/calendar data; verify coverage. | Some global coverage; verify HK/China field quality. | Best fundamentals complement for paid pilot. |
| Finnhub | Useful quotes and global coverage, but needs quality validation per market. | Useful fundamentals/earnings/filings-style endpoints. | Strong candidate for company news/sentiment enrichment. | Not primary for Options Engine. | Some economic/alternative data; verify. | Global coverage claims need market-specific testing. | Good enrichment candidate, not first-choice core quote/options provider. |
| Twelve Data | Good normalized quote/history API; already relevant to HK scanner enrichment. | Offers fundamentals, but verify depth versus FMP. | Not primary. | Not primary for US options decision engine. | Useful normalized macro/forex/ETF convenience layer. | Candidate for HK enrichment; China/HK license and completeness need proof. | Good multi-asset convenience provider; keep secondary until field QA passes. |
| Alpha Vantage | Useful free/low-cost time-series and technical indicators; rate limits can constrain workflows. | Offers fundamentals. | Offers news/sentiment API. | Offers US options category, but must validate chain depth, Greeks, IV/OI, and history before Options Engine use. | Good public-style economic indicators. | Limited/variable. | Good fallback/enrichment source, not the paid primary for high-confidence analysis. |
| Yahoo/yfinance | Useful research/dev fallback for prices, company info, and some options chains. | Inconsistent and unofficial. | Search/news availability exists but not licensed as product-grade feed. | Useful exploratory chain fetch, but not reliable for decision-grade IV/Greeks/OI/history. | Some tickers can proxy macro/rates. | Variable and unofficial. | Fallback only; do not label as licensed or decision-grade. |
| ORATS / Cboe / OPRA vendor category | Not primary for equities candles. | Not primary. | Not primary. | Strongest category for decision-grade options analytics, IV surface, Greeks, OI, chain history, and exchange-grade licensing. | Not primary. | Not primary. | Required evaluation path before public Options Decision Engine relies on live options data. |

## 4. Candidate provider matrix

| Provider | Latency | Field coverage | Options Greeks | Rate limits | Historical depth | Pricing/cost | License/redistribution risk | API stability | Credential/security burden | Fit for decision-grade analysis |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Alpaca | Good for authenticated HTTP/WebSocket market data; paid plans raise limits materially. | Strong US quotes/candles, snapshots, corporate actions; weak as full fundamentals/news provider. | Options feed is OPRA-backed on paid plan; verify Greeks/IV/OI exact fields before Options Engine use. | Published plan limits; free/basic limits are not enough for broad shared analysis. | Since 2016 per current docs for equities/options historical data. | Low-to-mid entry cost for individual paid plan; broker/business plans can be higher. | Exchange/feed terms apply; distinguish IEX, SIP, indicative options, and OPRA. | Good docs and SDKs. | Requires key/secret pair and feed entitlement management. | Good US quote/candle pilot; pair with FMP/Polygon/ORATS for research depth. |
| Polygon | Strong for US market data and WebSocket/REST use. | Broad stocks, reference, corporate actions, financials, news, options. | Strong candidate for Greeks, IV, OI, OPRA-sourced options coverage. | Paid tiers advertise high/unlimited API access; free tier is limited. | Paid stocks tiers can reach 20+ years; options docs emphasize historical/tick-level access. | Moderate-to-high depending on real-time, options, and business licensing. | Must review market-data terms, OPRA/exchange terms, display/non-display rights. | Good public docs, versioned APIs, client libraries. | API-key based; manageable but provider payloads and query params must stay sanitized. | Best broad US paid pilot if budget/license clears. |
| Tradier | Good for narrow brokerage/options market endpoints. | Quotes/options-oriented, not broad research coverage. | Chain endpoint supports Greeks flag and IV data courtesy of ORATS. | Verify plan-specific limits before shared use. | Better for current chains than deep historical research. | Often lower-friction than institutional vendors; final cost depends plan/account. | Brokerage/API terms and ORATS-derived data usage must be reviewed. | Good focused docs. | Bearer token; lower burden than broker session gateways. | Best first options adapter pilot, not full market data replacement. |
| IBKR | Good when connected and subscribed, but gateway/session and line limits matter. | Broad broker market access; research/fundamental/news varies by subscription. | TWS API returns option computation ticks and Greeks when option and underlying market-data subscriptions exist. | Concurrent market-data lines and subscription entitlements constrain scale. | Historical data available but pacing/subscription rules require careful testing. | Low exchange-pass-through fees for individual use; app-wide redistribution is not the same problem. | High risk if reused as shared provider; broker data is entitlement/account-bound. | Mature but operationally complex API/gateway. | High: TWS/IB Gateway session, account permissions, broker credentials, market-data acknowledgements. | Use for user-owned broker overlays, not default shared provider. |
| FMP | Adequate for non-HFT quote/history; not a primary realtime feed. | Strong fundamentals, ratios, profiles, financial statements, analyst-style data. | Weak/not primary for options chain analytics. | Plan bandwidth/API limits need sizing. | Strong financial-history claim; verify point-in-time behavior for reports. | Mid-cost fundamentals complement. | Terms of service and redistribution rights need review before public display/cache. | Good docs and stable REST patterns. | API-key based; low operational burden. | Best paid fundamentals complement. |
| Finnhub | Good for enrichment; market-specific quality should be sampled. | Fundamentals, earnings, filings, ownership, analyst/news-style coverage. | Not the Options Engine provider. | Free tier commonly attractive but shared usage needs paid limits. | Good for fundamentals/news history where endpoints support it. | Low-to-mid depending tier. | Review terms, source attribution, and redistribution. | Good docs/SDKs. | API-key based; low burden. | Good secondary enrichment for news/sentiment/fundamentals. |
| Twelve Data | Good normalized REST/WebSocket-style market data. | Stocks, ETFs, forex, crypto, fundamentals; depth varies by plan. | Not primary for US options. | Credits/plan limits must be modeled before scanner or analysis use. | Good for history, but verify per exchange/asset. | Low-to-mid paid plans; credit usage can surprise if broad scans expand. | Review exchange coverage and redistribution. | Good docs and multi-asset API shape. | API-key based; existing config shape is simple. | Good HK/multi-asset enrichment candidate, secondary to specialist providers. |
| Alpha Vantage | Adequate for low-volume enrichment; latency/rate limits often constrain interactive use. | Time series, fundamentals, news/sentiment, economic indicators, technicals, US options category. | Must be proven; do not assume Greeks/IV/OI completeness from category existence. | Free tier is too constrained for shared product routes. | Good endpoint variety; verify exact depth and adjusted data semantics. | Low-cost entry. | Terms and source rights require review. | Stable docs, simple API. | API-key based; low burden. | Useful fallback/enrichment, not first paid primary. |
| Yahoo/yfinance | Variable latency and stability; unofficial endpoint behavior can drift. | Broad but inconsistent. | Exploratory only; not reliable enough for IV/Greeks/OI decisions. | Unpublished/unofficial throttling. | Good for dev/research history, but not contractual. | Free. | High: yfinance states it is not affiliated with Yahoo and is intended for research/educational use. | Community library, not vendor contract. | No credentials, but high legal/stability burden. | Research fallback only. |
| ORATS / Cboe / OPRA vendor category | Strong for options workloads; latency depends product/feed. | Options-focused rather than broad market stack. | Strongest: Greeks, IV, OI, surfaces, chain history, quote intervals, analytics. | Published vendor/product limits or file/feed delivery terms; needs procurement review. | ORATS advertises data back to 2007; Cboe DataShop offers historical options datasets. | Highest likely cost and licensing complexity. | Highest need for display/non-display, redistribution, derived analytics, and OPRA/exchange review. | Institutional-grade docs/products. | API key/feed delivery plus commercial contract; high burden. | Required for production decision-grade options analytics. |

## 5. Recommended integration strategy

### Phase A: classification and tiering only

- Keep all paid provider adapters disabled by default.
- Add no API keys, config values, provider ordering changes, or live calls in this decision phase.
- Define data quality tiers before implementation:
  - `tier_0_unofficial_fallback`: yfinance/Yahoo-style or scraper-like data; local/dev/research only.
  - `tier_1_free_public`: free APIs or public feeds with limits; usable with clear fallback/freshness disclosure.
  - `tier_2_paid_standard`: authenticated paid API with documented fields, limits, and terms; suitable for user-visible analysis after QA.
  - `tier_3_exchange_or_options_licensed`: OPRA/Cboe/ORATS-style licensed options feed; required for decision-grade options analytics.
- Add route-level source disclosure requirements before changing any provider order.

### Phase B: dry-run provider circuit

- Route any future paid-provider pilot through provider circuit dry-run counters before live decision use.
- Record provider/category/route/failure buckets only; do not store raw URLs, query strings, payloads, symbols beyond approved labels, API keys, tokens, cookies, broker credentials, or stack traces.
- Track at minimum: success, timeout, provider_429, provider_403, provider_5xx, malformed_payload, insufficient_payload, auth_or_key_invalid, quota_policy_block, fallback depth, stale/cache-only served, and p95 latency bucket.
- Keep provider circuit enforcement disabled until a separately approved pilot changes behavior.

### Phase C: cache and freshness disclosure

- Every paid-provider response used in analysis should carry:
  - provider label;
  - category;
  - data quality tier;
  - as-of timestamp;
  - generated-at timestamp;
  - cache hit/miss/stale state;
  - entitlement/delay class where applicable;
  - missing-field list for decision-critical fields.
- Progressive enrichment may show partial data, but final decision-grade labels must not hide missing fundamentals, stale option chains, absent OI, absent Greeks, or synthetic/fallback data.

### Phase D: narrow pilots

| Pilot | Scope | Acceptance evidence | Stop condition |
| --- | --- | --- | --- |
| Polygon US equities | Quotes/candles/reference/news for a bounded symbol set. | Field completeness, latency buckets, rate-limit behavior, source/freshness disclosure, license review. | Any provider-order change, broad scanner integration, or live route defaulting before evidence. |
| FMP fundamentals | Financial statements, ratios, profiles, earnings/calendar fields for existing report needs. | Missing-field comparison versus current free providers, point-in-time limitations, cache policy. | Any report confidence upgrade without field QA. |
| Tradier options | One-symbol option-chain adapter dry run for bid/ask, volume, OI, IV, Greeks, expirations. | Options Decision Engine fixture-to-live field map, missing-field gating, delayed/realtime disclosure. | Any trading/actionability upgrade if Greeks/OI/IV/bid/ask are missing or delayed. |
| ORATS/Cboe category | Procurement/contract review and sample historical chain/Greek/OI data. | IV rank/percentile history, chain completeness, stale/holiday behavior, redistribution terms. | Treating broker/free option data as production-grade substitute. |
| Twelve Data HK | HK quote/history enrichment for bounded symbols. | Exchange coverage, latency, missing fields, Chinese/HK symbol normalization, license review. | Reordering China/HK providers without market-specific proof. |

## 6. Non-goals and protected boundaries

This task does not approve or implement:

- live provider integration;
- credential handling or `.env` changes;
- provider ordering or fallback changes;
- runtime provider circuit enforcement;
- provider quota enforcement;
- MarketCache TTL/SWR/cold-start/background refresh changes;
- Data Pipeline route behavior changes;
- Options Lab / Options Decision Engine runtime changes;
- scanner, backtest, portfolio, broker, notification, LLM, RBAC, API, frontend, tests, migrations, or config changes.

## 7. Decision summary

| Decision | Recommendation |
| --- | --- |
| Should WolfyStock replace free APIs immediately? | No. Keep free providers as fallback while adding paid-provider pilots behind disabled-by-default adapters. |
| Best broad US paid pilot | Polygon, with Alpaca as a simpler quote/candle alternative where its feed/plan fits. |
| Best fundamentals pilot | FMP first; Finnhub second as news/sentiment/fundamentals enrichment if quality and license pass. |
| Best options pilot | Tradier first for fast chain/Greeks integration learning; ORATS/Cboe/OPRA-vendor category for production-grade options analytics. |
| Should IBKR become a shared app data provider? | No. Keep IBKR user-owned/broker-overlay oriented unless a separate entitlement/security design approves more. |
| Should yfinance remain? | Yes, but only as unofficial research/dev/fallback tier with explicit license and confidence limitations. |
| What blocks decision-grade Options Engine output? | Missing or delayed option chain, bid/ask, OI, IV, Greeks, IV history, stale/fallback disclosure, and data license clearance. |

## 8. Sources reviewed

- Alpaca Market Data API docs and plan table: <https://docs.alpaca.markets/v1.3/docs/about-market-data-api>
- Polygon pricing and stocks/options docs: <https://polygon.io/pricing>, <https://www.polygon.io/docs/options>, <https://polygon.io/docs/rest/stocks/news>
- Tradier option-chain docs: <https://docs.tradier.com/reference/brokerage-api-markets-get-options-chains>
- IBKR market-data pricing/subscription and option computation docs: <https://api.ibkr.com/en/pricing/market-data-pricing.php>, <https://interactivebrokers.github.io/tws-api/option_computations.html>
- FMP pricing/developer docs: <https://site.financialmodelingprep.com/developer/docs/pricing/>
- Finnhub docs: <https://finnhubio.github.io/>
- Twelve Data docs: <https://twelvedata.com/docs>
- Alpha Vantage docs: <https://www.alphavantage.co/documentation/>
- yfinance package notice: <https://pypi.org/project/yfinance/>
- ORATS and Cboe options-data docs: <https://docs.orats.io/>, <https://orats.com/data-api>, <https://datashop.cboe.com/option-quote-intervals>, <https://datashop.cboe.com/faqs>
