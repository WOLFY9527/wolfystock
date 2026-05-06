# Options Lab Phase 0 Design

Date: 2026-05-06
Mode: docs-only product/data/API design. No runtime behavior changed.

## 1. Purpose

Options Lab / 期权实验室 is a professional options analysis surface for WolfyStock. It analyzes option contracts and strategies under explicit assumptions, then compares risk/reward structure, liquidity, IV, Greeks, breakeven, and scenario payoff.

It is an analysis-support module, not a trading engine. It must not place trades, connect to order execution, mutate portfolio accounting, or present guaranteed or personalized financial advice. Any ranking or score is an analytical view under user-provided assumptions, not a prediction or instruction.

The module must preserve all existing stock analysis, scanner, backtest, portfolio, provider, MarketCache, AI, notification, and DuckDB behavior. Phase 0 is only this design document.

## 2. User Stories

- "I want to buy TEM options. Should I consider call or put?"
- "If I am bullish on TEM over 1-3 months, which expiration/strike has better risk/reward?"
- "What happens if TEM rises 10%, stays flat, or drops 10%?"
- "Is naked long call better than a call spread?"
- "Is IV too expensive relative to the move I need?"
- "Which contracts should be avoided because bid/ask spread or OI is poor?"
- "If I have a fixed premium budget, which structures keep max loss bounded?"
- "What changes if earnings arrives before expiration?"

## 3. Product Positioning And Non-Goals

Positioning:

- Analytical lab for option contracts and strategy structures.
- Scenario simulator for price/date/IV assumptions.
- Contract screener for liquidity, moneyness, DTE, IV, and Greeks.
- Strategy comparator for single-leg long options and defined-risk debit spreads.
- Risk explainer that makes premium loss, breakeven difficulty, theta decay, and liquidity constraints visible.

Non-goals:

- No order placement.
- No broker execution.
- No naked option selling in MVP.
- No guarantee, certainty, or personalized financial advice.
- No hidden leverage encouragement.
- No replacement for suitability checks, risk controls, or broker margin rules.
- No raw provider payload viewer.
- No portfolio accounting changes.
- No options order routing, option exercise, assignment, or margin engine.

## 4. Core Concepts

| Concept | Definition for Options Lab |
| --- | --- |
| Underlying price | Latest normalized price for the equity or ETF under analysis, with source and freshness displayed. |
| Expiration | Contract expiration date. UI should show calendar date and DTE. |
| Strike | Contract exercise price. |
| Call / Put | Call benefits from upside exposure; put benefits from downside exposure. Directional language must stay scenario-based. |
| Bid / ask / mid | Best visible bid, ask, and midpoint. Mid is only an analytical reference, not a fill guarantee. |
| Volume / open interest | Same-day activity and outstanding contracts. Low values reduce confidence and liquidity score. |
| Implied volatility | Market-implied volatility from provider or computed model input. High IV can make long premium structures expensive. |
| Historical volatility | Realized underlying volatility over configurable lookbacks; used as context, not a forecast. |
| IV percentile / IV rank | Optional context if the data source supports historical IV. If unavailable, display as unavailable rather than fabricate it. |
| Delta / gamma / theta / vega / rho | Greeks from provider or computed model. If computed internally, show model assumptions and inputs. |
| Breakeven | Underlying price at expiration where gross payoff offsets premium/debit. |
| Intrinsic / extrinsic value | In-the-money value and time/volatility value embedded in premium. |
| Moneyness | ITM / ATM / OTM classification relative to underlying price. |
| DTE | Days to expiration. Short DTE increases theta and path sensitivity. |
| Liquidity | Composite view of bid/ask width, volume, OI, quote age, and contract availability. |
| Spread % | `(ask - bid) / mid` or `(ask - bid) / ask` depending on final implementation; formula must be shown. |
| Max loss / max gain | Strategy-level bounded loss/gain, with undefined or theoretically large risk excluded from MVP. |
| Payoff at expiration | Deterministic payoff from terminal underlying price minus debit/credit and fees if modeled. |
| Payoff before expiration | Theoretical mark-to-market requiring model assumptions, IV, rates, dividends, and time remaining. |
| Probability estimate caveats | Any probability-like output depends on assumptions and must be labeled as modeled estimate, not real-world certainty. |

## 5. MVP Scope

MVP should support:

- US listed equity options first.
- Single underlying symbol input.
- Option chain display.
- Expiration selector.
- Call/put table.
- Contract score with explanation.
- Liquidity filter.
- Scenario payoff at target price/date.
- Basic strategy comparison:
  - long call
  - long put
  - bull call spread
  - bear put spread
  - cash-secured put / covered call as analysis-only only if existing portfolio context is reliable and explicitly read-only
- No order placement.
- No naked short options.
- No margin/risk engine in MVP.
- No broker mutation or portfolio accounting mutation.

## 6. Data-Source Audit

Static inspection found existing market-data infrastructure, but no current Options Lab runtime surface:

- No `/api/v1/options` route is registered in `api/v1/router.py`.
- `data_provider/` has quote/history/fundamental adapters for A-share, HK, and US stock analysis, including yfinance, FMP, Finnhub, Alpha Vantage, Alpaca, Twelve Data, AkShare, Tushare, pytdx, baostock, and efinance.
- `data_provider/yfinance_fetcher.py` uses yfinance for OHLCV and realtime/near-realtime quote fallback, but does not expose `Ticker.options` or `option_chain`.
- `data_provider/us_fundamentals_provider.py` exposes FMP/Finnhub/yfinance fundamentals, quote, historical price, and technical indicator helpers. No options-chain helper was found.
- `data_provider/alpaca_fetcher.py` exposes US stock bars, snapshots, latest quote, and realtime quote. No options-chain helper was found.
- `data_provider/twelve_data_fetcher.py` exposes HK/US daily data and quote. No options-chain helper was found.
- `src/services/analysis_provider_planner.py` has category-level chains for stock_name/profile/quote/historical_prices/technical_indicators/fundamentals/earnings/news/sentiment/macro. No options category was found.
- `src/services/market_cache.py` and `src/services/market_overview_service.py` provide useful cache/freshness patterns, but they are market-panel oriented and must not be changed by Phase 0.

Provider capability conclusions are intentionally conservative. Static repo inspection can identify code paths already implemented, but it cannot prove whether a provider account, plan, or API supports options-chain fields. Anything not implemented in this repo is marked "unknown; needs live-provider validation later."

| Data need | Required for MVP? | Existing source in repo? | Candidate provider | Reliability risk | Cache/freshness note | Privacy/secrets note |
| --- | --- | --- | --- | --- | --- | --- |
| Underlying quote | Yes | Yes: `DataFetcherManager.get_realtime_quote()`, yfinance, Alpaca when configured, FMP/Finnhub quote helpers | Existing normalized quote path; Alpaca/FMP/Finnhub/yfinance | Realtime may be delayed, unavailable, or fallback-only; multiple providers are memory-cache scoped | Short TTL; display quote `asOf`, source, delay/stale status | Env var names only, e.g. `ALPACA_API_KEY_ID`, `ALPACA_API_SECRET_KEY`, `FMP_API_KEY`, `FINNHUB_API_KEY`; never values |
| Option expirations | Yes | No current adapter found | yfinance, Tradier, Polygon, marketdata.app, FMP/Finnhub if plan supports options | Unknown; needs live-provider validation later | Very short TTL during market hours; longer after market close | No raw provider payload; no API key display |
| Option chain | Yes | No current adapter found | yfinance, Tradier, Polygon, marketdata.app, FMP/Finnhub if plan supports options | Unknown; fields and entitlement vary by provider | Chain `asOf` required; stale warning required | Normalize and sanitize; no raw provider JSON in UI |
| Quote bid/ask/mid | Yes | Underlying bid/ask not normalized broadly; option bid/ask not found | Dedicated options provider or yfinance chain if validated | Critical risk: delayed quotes or missing bid/ask can distort liquidity | Short TTL; reject stale bid/ask for ranking unless user accepts stale view | No raw quote payload; no request URL/query with keys |
| Volume/OI | Yes | Not for options | Dedicated options provider or yfinance chain if validated | OI may update daily; volume intraday can be delayed | Show separate `volumeAsOf` and `openInterestAsOf` if possible | Safe numeric fields only |
| IV | Yes | Not for options | Dedicated options provider or yfinance chain if validated | Provider IV definitions vary; missing IV must not be fabricated | Cache with chain; show provider/model source | No raw provider payload |
| Greeks | Required for pro analysis; MVP can degrade if unavailable | No options Greeks path found | Provider-supplied Greeks, or internal model in later phase | Provider may omit Greeks; internal model needs assumptions | If computed, cache derived values with model inputs/version | No model secrets; no raw payload |
| Earnings/event dates | Strongly useful | Partial: fundamentals/earnings context exists for stock analysis | Existing FMP/yfinance/Alpha/Finnhub earnings paths if normalized later | Dates may be missing or stale | Daily TTL acceptable; show event source | Env var names only |
| Dividends | Useful for pricing/early-exercise context | Partial via fundamental pipeline for stock analysis | Existing yfinance/FMP/fundamental adapter if normalized later | Dividend timing affects options; missing data must be caveated | Daily TTL acceptable | Safe public fields only |
| Risk-free rate | Useful for theoretical pricing | Macro/rates panel exists, but no pricing input contract | Treasury/rates source, config default, or provider | Incorrect rate has smaller but real pricing impact | Daily TTL likely enough | No secrets |
| Historical volatility | Yes for IV context | Existing OHLCV history paths support realized vol computation later | Existing history providers, local stock_daily, yfinance/FMP/Alpaca | History gaps, split/corporate-action adjustment differences | Cache realized vol by symbol/lookback/source | No raw payload |
| Corporate actions | Useful | Partial through adjusted history and fundamental/dividend paths; no options-specific adjustment contract | yfinance/FMP/provider metadata | Splits can invalidate strike comparisons if mishandled | Daily TTL; mark adjusted/unadjusted source | No raw payload |
| Contract metadata | Yes | No options contract metadata path found | Dedicated options provider or yfinance chain if validated | OCC symbology, multiplier, exercise style, and deliverables can vary | Cache by expiration/contract symbol; validate multiplier | No raw payload or credentials |

## 7. Proposed Backend API Contract

Design only. Do not implement in Phase 0.

### `GET /api/v1/options/underlyings/{symbol}/summary`

Purpose: return normalized underlying snapshot, supported-market status, data-source freshness, and options availability status.

Params: `symbol`, optional `forceRefresh=false`.

Response sketch:

```json
{
  "symbol": "TEM",
  "market": "us",
  "underlying": {
    "price": 52.34,
    "changePct": 1.2,
    "source": "alpaca",
    "asOf": "2026-05-06T09:45:00-04:00",
    "freshness": "delayed"
  },
  "optionsAvailability": {
    "supported": true,
    "provider": "unknown",
    "limitations": ["provider_validation_required"]
  },
  "metadata": {
    "readOnly": true,
    "noExternalCallsInTests": true
  }
}
```

Cache/freshness: quote TTL short; options availability can be cached longer. Failure states: unsupported market, missing symbol, provider unavailable, stale quote. Privacy: no raw provider payload or secrets. Tests required: symbol normalization, unsupported market, stale quote, no secret fields.

### `GET /api/v1/options/underlyings/{symbol}/expirations`

Purpose: list available expirations with DTE, monthly/weekly tags, and data freshness.

Params: `symbol`, optional `minDte`, `maxDte`, `forceRefresh=false`.

Response sketch: `expirations[]` with `date`, `dte`, `type`, `chainAvailable`, `asOf`, `source`, `warnings`.

Cache/freshness: short TTL during market hours; stale warning required. Failure states: no expirations, provider missing entitlement, stale provider data. Privacy: no raw payload. Tests: empty chain, provider failure, stale data, unsupported symbol.

### `GET /api/v1/options/underlyings/{symbol}/chain`

Purpose: return normalized calls/puts for selected expiration(s), with liquidity and data-confidence metadata.

Params: `symbol`, `expiration`, optional `side=call|put|both`, `minOpenInterest`, `maxSpreadPct`, `includeGreeks=true`.

Response sketch: `underlying`, `expiration`, `calls[]`, `puts[]`, `filtersApplied`, `chainAsOf`, `source`, `limitations`.

Cache/freshness: option chain TTL should be short; show `chainAsOf` and stale flags. Failure states: provider failure, no contracts, unsupported expiration, missing bid/ask, entitlement. Privacy: normalized contracts only; no raw provider JSON. Tests: safe normalized contracts, empty chain, no secrets, deterministic fixture response.

### `POST /api/v1/options/analyze`

Purpose: analyze candidate contracts under user assumptions and return ranking explanations, risk warnings, and limitations.

Request example:

```json
{
  "symbol": "TEM",
  "direction": "bullish",
  "targetPrice": 65,
  "targetDate": "2026-08-21",
  "maxPremium": 1000,
  "riskProfile": "aggressive",
  "strategies": ["long_call", "bull_call_spread"],
  "forceRefresh": false
}
```

Response sections:

- `underlying`
- `assumptions`
- `optionChainSummary`
- `candidateContracts`
- `strategyComparisons`
- `scenarioPayoff`
- `risks`
- `limitations`
- `metadata`

Cache/freshness: can reuse current normalized chain if fresh; `forceRefresh` later must be rate-limited. Failure states: invalid assumptions, chain unavailable, no contracts after filters, stale data accepted only with warning. Privacy: no raw payload, no account data. Tests: deterministic scoring fixture, invalid budget/profile, no external calls in tests.

### `POST /api/v1/options/strategies/compare`

Purpose: compare normalized strategy legs under explicit assumptions.

Body: `symbol`, `underlyingPrice`, `legs[]`, `targetPrices[]`, `targetDates[]`, `ivShock[]`, `riskBudget`, optional `portfolioContextRef` only in later phases.

Response sketch: `strategies[]` with max loss, max gain, breakeven, required move, IV/theta sensitivity, liquidity warnings, and suitability notes by risk profile.

Cache/freshness: computed from supplied or fresh chain data; derived result can be cached by safe hash if no user/account data. Failure states: invalid leg composition, naked short detected, unsupported strategy, stale chain. Tests: long call, long put, debit spreads, naked short rejection.

### `POST /api/v1/options/scenario`

Purpose: compute payoff grid for contracts/strategies across price, date, and IV shocks.

Body: `symbol`, `strategy`, `priceGrid`, `dateGrid`, `ivShockGrid`, `modelAssumptions`.

Response sketch: `payoffAtExpiration`, `theoreticalBeforeExpiration`, `riskTable`, `modelLimitations`, `metadata`.

Cache/freshness: derived result tied to chain `asOf`, model version, assumptions. Failure states: missing IV/Greeks, unsupported pre-expiration pricing, invalid date. Tests: expiration payoff deterministic, pre-expiration unavailable when model disabled, IV shock labels.

## 8. Contract Scoring Model

The contract score is an analytical ranking under assumptions. It is not a guarantee, signal, or instruction.

Formula sketch:

```text
score = weighted_sum(
  directional_fit,
  delta_fit,
  breakeven_difficulty,
  premium_efficiency,
  liquidity_score,
  bid_ask_spread_penalty,
  iv_value_signal,
  theta_decay_risk,
  dte_fit,
  target_scenario_payoff,
  max_loss_budget_fit,
  oi_volume_confidence,
  event_earnings_risk,
  data_freshness_confidence
)
```

All sub-scores should be bounded, for example `0..100` before weighting. Weights must be configurable later and displayed as model metadata. They must not be hardcoded as product truth.

Suggested sub-score meanings:

| Sub-score | Direction |
| --- | --- |
| Directional fit | Rewards call/put/strategy alignment with user scenario. |
| Delta fit | Penalizes contracts that are too low-delta for directional thesis or too high-cost for budget. |
| Breakeven difficulty | Penalizes high required move versus target and realized volatility. |
| Premium efficiency | Rewards exposure per premium at risk, bounded by liquidity and theta risk. |
| Liquidity score | Rewards tight spread, higher OI, higher volume, fresh quote. |
| Bid/ask spread penalty | Penalizes wide spread and stale quotes. |
| IV value signal | Flags expensive/cheap only relative to available IV/HV/IV-rank context; unavailable stays neutral with limitation. |
| Theta decay risk | Penalizes high daily decay relative to premium and target date. |
| DTE fit | Rewards expiration that covers target date with enough time buffer. |
| Target scenario payoff | Rewards payoff under provided target price/date, net of premium. |
| Max loss budget fit | Penalizes premium/debit above user budget. |
| OI/volume confidence | Penalizes low confidence even if payoff looks attractive. |
| Event/earnings risk | Flags event before expiration; direction of impact is not assumed. |
| Data freshness confidence | Penalizes stale chain, stale underlying quote, missing IV/Greeks. |

Score output must include explanation rows:

- `score`
- `gradeLabel`
- `topPositiveDrivers`
- `topRiskDrivers`
- `assumptionsUsed`
- `dataConfidence`
- `notAdviceDisclosure`

Allowed style: "在该情景假设下风险收益结构较优". Avoid command-style recommendation.

## 9. Strategy Comparison Model

| Strategy | When it fits | Max loss | Max gain | Breakeven | IV sensitivity | Theta sensitivity | Liquidity requirements | Account/risk notes | MVP status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Long call | Bullish directional scenario with defined premium risk | Premium paid | Theoretically unlimited upside before costs | Strike + premium | Long vega; high IV can hurt | Negative theta | Tight call spread, OI/volume acceptable | Can lose 100% of premium | MVP |
| Long put | Bearish directional scenario with defined premium risk | Premium paid | Large but bounded by underlying approaching zero | Strike - premium | Long vega; high IV can hurt | Negative theta | Tight put spread, OI/volume acceptable | Can lose 100% of premium | MVP |
| Bull call spread | Bullish scenario with capped upside and lower debit | Net debit | Width - net debit | Lower strike + net debit | Lower vega than naked long call | Usually lower theta drag | Both legs liquid; avoid legging assumptions | Defined risk; capped upside | MVP |
| Bear put spread | Bearish scenario with capped downside payoff and lower debit | Net debit | Width - net debit | Higher strike - net debit | Lower vega than naked long put | Usually lower theta drag | Both legs liquid | Defined risk; capped payoff | MVP |
| Straddle | Volatility thesis around major move, direction uncertain | Net debit | Large both directions | Two breakevens | Strong long vega | High negative theta | Very liquid ATM contracts | Advanced and high premium decay | Later/advanced |
| Strangle | Volatility thesis with wider move required | Net debit | Large both directions | Two wider breakevens | Strong long vega | Negative theta | Liquid OTM contracts | Lower debit but harder breakeven | Later/advanced |
| Covered call | Income/overwrite against owned shares | Opportunity loss plus share downside | Premium plus capped upside | Stock basis adjusted by premium | Short vega | Positive theta | Stock ownership and call liquidity | Needs reliable portfolio context | Later |
| Cash-secured put | Willingness to buy shares at effective price | Assignment/capital risk less premium | Premium received | Strike - premium | Short vega | Positive theta | Put liquidity and cash availability | Requires cash/assignment suitability checks | Later or analysis-only |
| Protective put | Downside hedge for owned shares | Premium plus residual stock risk | Stock upside less premium | Stock basis + premium | Long vega | Negative theta | Put liquidity | Needs reliable holdings context | Later |
| Collar | Stock hedge with financed put/call cap | Defined stock downside band | Capped upside | Depends on stock basis, put, call | Mixed | Mixed | Both legs liquid | Needs holdings, tax/account context | Later |

For MVP, include long call, long put, and debit spreads. Covered call, cash-secured put, protective put, and collar wait for a separate portfolio safety review. Straddle/strangle can be displayed as advanced educational comparisons only after risk language and IV caveats are strong. Naked short calls/puts are out of scope.

## 10. Scenario Analysis

Scenario outputs:

- Payoff at expiration.
- Approximate mark-to-market before expiration only if a pricing model and assumptions are available.
- Target price grid:
  - -20%
  - -10%
  - flat
  - +10%
  - +20%
  - custom target
- Date grid:
  - today
  - 1 week
  - 2 weeks
  - target date
  - expiration
- IV shock:
  - IV -20%
  - IV unchanged
  - IV +20%
- Risk table:
  - premium at risk
  - breakeven
  - required move
  - theta decay estimate
  - liquidity warning

Pre-expiration theoretical pricing requires a model and assumptions: underlying price, time to expiration, IV, dividends, risk-free rate, exercise style, and transaction-cost assumptions. If provider Greeks or IV are unavailable, the UI must say so and either omit pre-expiration pricing or mark it as model-limited.

## 11. Frontend UX Contract

Proposed route: `/zh/options-lab`

Chinese nav label: `期权实验室`

Page sections:

- Underlying input/search.
- Assumption panel:
  - direction: 看涨 / 看跌 / 中性 / 赌波动
  - target price
  - target date
  - risk budget
  - risk profile
- Underlying snapshot.
- Expiration/strike filters.
- Calls/puts chain table.
- Candidate ranking.
- Strategy comparison cards.
- Scenario payoff matrix.
- Risk warnings.
- Collapsed developer/freshness details.

Design style:

- WolfyStock OLED/deep-space/ghost-glass.
- Dense professional terminal.
- No loud casino/gambling visual language.
- No "buy now" CTA.
- No default native controls.
- Chinese labels by default.
- Raw provider data collapsed and sanitized.
- Freshness/source details visible enough for trust, but raw provider payload hidden.

Primary actions should be analytical verbs: `分析情景`, `比较策略`, `查看风险`, `刷新行情` if future rate limits allow. Avoid command-style trade CTAs.

## 12. Risk Language And UI Copy

Approved wording examples:

- "该结果基于你输入的方向、目标价与时间窗口。"
- "期权可能归零，最大亏损可能达到全部权利金。"
- "评分表示情景假设下的风险收益结构，不代表确定收益。"
- "IV 偏高时，即使方向判断正确，合约仍可能亏损。"
- "价差过宽或 OI 较低的合约可能难以成交或滑点较大。"
- "该模块不提供下单或保证性收益建议。"
- "在该情景假设下风险收益结构较优。"
- "IV 偏高，裸买期权风险较大。"
- "该合约 breakeven 较高，需要更强方向性走势。"
- "流动性不足，不适合作为优先候选。"

Rejected wording:

- "稳赚"
- "必买"
- "最值得买"
- "确定盈利"
- "无风险"
- "保证翻倍"
- "AI 建议你买入"
- "all in"
- "risk-free income"

## 13. Security, Privacy, And Compliance

Rules:

- No broker execution.
- No account mutation.
- No raw API key display.
- No secret/provider payload display.
- No personalized suitability claim unless a separate suitability module exists.
- No storing raw option chain payload unless a storage policy exists.
- No trading recommendation phrased as command.
- All AI explanations must include assumptions and risk caveats.
- Scores are analytical rankings under assumptions, not guarantees.
- Options are high risk and can expire worthless.
- Single-leg long options can lose 100% of premium.
- Spreads have defined but still material risks.
- Selling naked options is excluded from MVP.

Data handling:

- Normalize provider data into safe contracts before API response.
- Do not expose request URLs, provider headers, raw exception text, or provider response bodies.
- Mention env var names only, never values.
- If portfolio context is introduced later, use read-only projections and explicit user consent. No broker token, broker payload, account credential, or raw account data should be shown.

## 14. Caching And Freshness

Design:

- Option chains should have short TTL.
- Underlying quote freshness displayed.
- Option chain `asOf` displayed.
- Stale data warning displayed.
- Market closed / delayed data warning displayed.
- `forceRefresh` available later but rate-limited.
- No cache mutation in Phase 0.
- No provider calls in this docs task.

Suggested freshness model:

| Data | Market-hours TTL concept | After-hours TTL concept | Required UI metadata |
| --- | --- | --- | --- |
| Underlying quote | seconds to low minutes | longer, marked closed/delayed | source, `asOf`, freshness |
| Option chain bid/ask | seconds to low minutes | longer, marked closed/delayed | chain `asOf`, quote age, provider |
| OI | daily or provider-defined | daily | OI date/source |
| IV/Greeks | tied to chain quote | tied to chain quote | provider/computed, model version |
| Historical volatility | daily | daily | lookback/source |
| Earnings/dividends | daily | daily | event source/date |

## 15. Testing Plan For Future Implementation

Backend tests:

- Chain endpoint returns safe normalized contracts.
- Missing symbol.
- Unsupported market.
- Empty chain.
- Provider failure.
- Stale/fallback state.
- No raw provider payload/secrets.
- Scoring deterministic under fixture.
- No external calls in tests.
- Naked short strategy rejected.
- `forceRefresh` does not bypass rate controls in tests unless explicitly mocked.

Frontend tests:

- Route renders.
- Assumption panel.
- Calls/puts table.
- Strategy comparison.
- Scenario table.
- Risk warnings visible.
- No secret/raw payload in DOM.
- Loading/empty/error/stale states.
- Desktop/mobile no overflow.
- Chinese labels default for `/zh/options-lab`.
- No "buy now" or command-style trade CTA.

Playwright:

- `/zh/options-lab` desktop 1440x1000.
- `/zh/options-lab` mobile 390x844.
- Mocked API only.
- No live provider calls.
- No broker/account data.

## 16. Implementation Sequencing

Phase 0:

- This design doc.

Phase 1:

- Backend data-source adapter and normalized option chain API with mocked tests.
- Add no frontend dependency on live providers.
- Preserve provider ordering and cache behavior outside the new options namespace.

Phase 1 implementation note (2026-05-06):

- Delivered a fixture-backed backend-only `TEM` option chain API with safe normalized schemas, no live provider/LLM/broker calls in tests, and read-only limitations metadata. Scoring, scenario comparison, and portfolio/broker integration remain deferred.

Phase 2:

- Options Lab frontend with mocked data and no live provider dependency.
- Chinese-first route `/zh/options-lab`.
- Risk warnings visible in all non-empty result states.

Phase 3:

- Scoring and scenario simulation with deterministic fixture tests.
- Score explanation required for every ranked candidate.

Phase 4:

- Strategy comparison.
- Include long call, long put, bull call spread, and bear put spread first.

Phase 5:

- Optional integration with portfolio context and covered/collar strategies after risk review.
- Read-only projections only; no broker execution.

Phase 6:

- Advanced implied volatility and probability analytics.
- Add IV percentile/rank only if historical IV data is reliable.

## 17. Parallelization Plan

| Task | Can run in parallel with | Must wait for | Likely files touched | Risk |
| --- | --- | --- | --- | --- |
| Backend option chain adapter | Frontend shell using mocked contract | Phase 0 API contract | `api/v1/endpoints/options.py`, `api/v1/schemas/options.py`, new service/adapter tests | Medium; provider entitlement and freshness semantics |
| Provider capability validation | Docs/frontend mocked work | Approved provider list and no-secret test harness | Dedicated provider validation docs/tests only | Medium; must not print secrets or call live APIs in normal tests |
| Normalized option-chain fixtures | Frontend shell, scoring design | Draft schema fields | `tests/fixtures/options/*.json`, schema tests | Low if synthetic only |
| Scoring engine | Frontend mocked table after score response sketch | Backend normalization shape | New options scoring service/tests | Medium; avoid score-as-advice language |
| Scenario engine | Frontend payoff matrix mock | Strategy/contract model | New options scenario service/tests | Medium; pre-expiration model caveats |
| Frontend Options Lab shell | Backend adapter/scoring if mocked API stable | Route/i18n/nav decision | `apps/dsa-web/src/...` | Medium; visual and risk-copy acceptance |
| Strategy comparison | Frontend shell and scoring docs | Normalized legs and pricing assumptions | Backend strategy service/tests, frontend strategy cards | Medium; naked short exclusion |
| Portfolio-linked strategies | Nothing in MVP | Portfolio safety review and read-only context contract | Portfolio read-only projection integration | High; account suitability and broker data risk |
| Broker execution | Should not be created | Separate explicit product/legal approval | None in this roadmap | Prohibited for MVP |

## 18. Recommended Next Codex Prompts

1. Options Lab Phase 1 backend option chain API + normalized fixtures

   Safety constraints: backend-only; no frontend; no live provider calls in tests; no broker execution; no portfolio accounting changes; no provider ordering changes outside new options namespace; no raw provider payloads or secrets; fixture-based tests only.

2. Options Lab Phase 2 frontend shell + mocked option chain

   Safety constraints: frontend-only; mocked API data; no backend implementation; no live providers; Chinese-first `/zh/options-lab`; risk warnings visible; no order-placement CTA; no investment-advice commands; no raw provider payload in DOM.

3. Options Lab Phase 3 scoring/scenario engine

   Safety constraints: deterministic fixtures; score is analytical ranking under assumptions; no guarantee language; no naked short strategies; no live provider/LLM calls; no portfolio mutation; all outputs include assumptions, risks, limitations, and data freshness.
