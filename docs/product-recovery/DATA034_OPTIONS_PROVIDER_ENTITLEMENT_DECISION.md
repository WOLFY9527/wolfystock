# DATA-034 Options Provider Entitlement Decision

Task ID: DATA-034

Status: internal decision record and implementation gate. This file does not
approve provider code, UI changes, credentials, network behavior, cache/runtime
behavior, backtest behavior, broker behavior, or strategy ranking behavior.

Repository basis:

- `docs/product-recovery/DATA_COVERAGE_MATRIX.md` says Options contracts and
  normalizers exist, but no repository path proves an authorized live options
  provider is enabled.
- `docs/archive/product-recovery/acceptance/DATA021_REAL_DATA_VALUE_ACCEPTANCE.md` accepts the
  Options Lab chain readiness boundary only. It does not add a live provider,
  OPRA/vendor rights proof, redisplay approval, strategy ranking,
  GEX/vanna/charm, or trade workflow.
- `docs/audits/options-provider-adapter-contract.md` keeps current fixture,
  dry-run, stub, and adapter-contract paths below decision authority.
- `docs/options/options-market-structure-observation-contract.md` and
  `docs/options/options-market-structure-prerequisite-manifest.md` keep future
  market-structure evidence observation-only until methodology, rights,
  coverage, freshness, DTO/API, provider/cache, frontend, and no-advice gates
  are separately approved.

## 1. Executive decision boundary

What Options Lab can claim today:

- A read-only, analysis-only options research workspace exists.
- The current contracts can represent normalized option-chain fields such as
  expiration, strike, side, bid/ask/mid/last, volume, open interest, IV, Greeks,
  multiplier, freshness, and provider/data-quality metadata.
- `optionsChainReadiness` can classify missing configuration, demo/sample
  chains, sparse coverage, missing IV/Greeks/open-interest/volume/quote fields,
  and complete authorized-chain-shaped inputs.
- Fixture, dry-run, stub, and adapter-contract data can support deterministic
  observation, contract-shape tests, payoff examples, and fail-closed gate tests.
- Current outputs must remain no-broker, no-order, no-portfolio-mutation,
  no-personalized-instruction, and observation-only unless a later protected
  task explicitly changes that boundary.

What Options Lab cannot claim until provider and entitlement evidence exists:

- It cannot claim an authorized live or delayed options chain for production use.
- It cannot claim OPRA or equivalent rights, vendor redisplay approval, storage
  approval, historical chain rights, or public-beta display rights.
- It cannot claim score-authoritative strategy selection, strategy probability,
  historical options backtesting, historical win-rate evidence, IV-rank authority,
  or provider-authoritative Greeks.
- It cannot claim GEX, gamma flip, vanna, charm, zero-DTE, dealer-positioning, or
  wall/concentration evidence as implemented, approved, or stronger than
  observation.
- It cannot infer rights from provider names, provider self-claims, pricing
  pages, fixture completeness, dry-run output, cached output, or a normalized
  payload that happens to contain all fields.

## 2. Required data capabilities

Minimum data capabilities before any stronger Options Lab claim:

| Capability | Required evidence | Fail-closed rule |
| --- | --- | --- |
| Live or delayed option chain | Authorized chain for the selected underlying with chain `asOf`, quote `asOf`, delay class, market-session handling, and provider identity. | Missing or unverified chain stays blocked or observation-only. |
| Expiration coverage | Clear expiration list, DTE, weekly/monthly classification where available, selected-expiration coverage, and excluded-expiration handling. | Single or sparse expiration coverage cannot support score-authoritative output. |
| Strike coverage | Covered strike set by expiration, moneyness range, and sparse-strike detection. | Sparse or one-sided strike coverage stays partial. |
| Bid/ask/mid/last | Complete quote fields, quote timestamp, spread rule, and stale quote downgrade. | Missing bid/ask/last or invalid spreads block score-authoritative use. |
| IV | Provider-supplied or model-computed IV with source, timestamp, methodology, and missing-field policy. | Missing or methodology-unknown IV blocks IV-dependent outputs. |
| Greeks | Delta, gamma, theta, vega, rho where required, plus provider/model source and model version if computed internally. | Missing Greeks block GEX, vanna, charm, and model-sensitive strategy outputs. |
| Open interest | OI value, OI date, update cadence, and holiday/session handling. | Missing or stale OI blocks OI concentration, GEX, and dealer-positioning evidence. |
| Volume | Intraday or delayed volume with timestamp and source. | Missing volume lowers liquidity confidence and blocks score-authoritative liquidity ranking. |
| Underlying price freshness | Underlying spot/reference price, timestamp, source, delay/stale class, and corporate-action handling. | Stale or unauthorized spot keeps all derived outputs observation-only. |
| Historical option-chain data | Point-in-time chain snapshots with quotes, IV, Greeks, OI, volume, expirations, strikes, and as-of timestamps. | No historical chain means no historical strategy backtest, no historical win-rate display, and no IV-rank authority. |
| Corporate-action adjusted underlying history | Adjusted underlying OHLCV, split/dividend handling, deliverable/multiplier checks, and source lineage. | Unadjusted or unknown adjustment history blocks backtest and probability-model authority. |
| Risk-free rate and dividend assumptions | Rate source, dividend assumptions, timestamp, model usage, and sensitivity disclosure. | Missing assumptions keep probability and theoretical pricing outputs model-limited. |

## 3. Entitlement and rights checklist

Before any score-authoritative Options Lab output, attach a reviewable evidence
bundle covering every item below:

| Checklist item | Evidence required | Blocking condition |
| --- | --- | --- |
| OPRA or equivalent rights | Contract, account, plan, or vendor evidence proving access to required US options fields, including OPRA/OCC/exchange/licensed-source backing where applicable. | Provider name or endpoint access alone is not enough. |
| Vendor terms | Terms covering intended use, display, derived analytics, storage, and audit retention. | Unknown or personal-only terms keep output observation-only. |
| Redistribution / redisplay boundary | Clear statement of what can be shown to end users, operators, exports, screenshots, and support artifacts. | Redisplay ambiguity blocks public or beta user display. |
| Personal-use vs public-beta distinction | Explicit split between individual research use and multi-user public-beta display. | Broker/account-bound or personal-use data cannot become shared app data. |
| Delayed vs real-time labeling | Provider delay class, exchange delay, as-of fields, and UI/API label requirements. | Missing delay label blocks freshness-sensitive output. |
| Storage rights | Permission for normalized snapshots, derived metrics, audit evidence, and retention duration. | No storage rights means no durable chain snapshots or replay evidence. |
| Historical data rights | Permission and depth for historical option chains, IV, Greeks, OI, volume, corporate actions, and point-in-time replay. | No historical rights means no historical options backtest or win-rate evidence. |
| Audit evidence before score-authoritative output | Sanitized proof artifact with reviewer, date, source, evidence location, expiry trigger, and no secrets. | Missing audit proof keeps `scoreAuthority` blocked. |

## 4. Strategy Lab dependency matrix

Legend:

- `Model-implied today` means the current repo can only support a bounded,
  fixture/supplied-input calculation without authorized market-data authority.
- `Historical chain required` means a credible historical evaluation needs
  point-in-time options chains, not only current chain fields.
- `Allowed authority` is the strongest allowed posture before provider,
  entitlement, methodology, and historical evidence gates pass.

| Strategy / metric | Required fields | Model-implied today | Historical chain required | Allowed authority before gates pass | Evidence blockers |
| --- | --- | --- | --- | --- | --- |
| Straddle | ATM call/put legs, bid/ask/mid/last, IV, Greeks, OI, volume, underlying spot, expiration, rate/dividend assumptions. | No product claim; fixture/supplied legs can only illustrate payoff. | Yes for historical performance or win-rate evidence. | Observation-only. | Authorized chain, IV/Greeks, OI/volume, spread, event/calendar, historical chain, rights. |
| Strangle | OTM call/put legs, strikes by moneyness, bid/ask/mid/last, IV, Greeks, OI, volume, underlying spot, expiration, rate/dividend assumptions. | No product claim; fixture/supplied legs can only illustrate payoff. | Yes for historical performance or win-rate evidence. | Observation-only. | Strike coverage, liquidity, IV surface, historical chain, rights. |
| Vertical spread | Two same-side legs, ordered strikes, bid/ask/mid/last, IV, Greeks, OI, volume, expiration, underlying spot. | Limited fixture/supplied-leg payoff only. | Yes for historical performance or win-rate evidence. | Observation-only. | Multi-leg quote quality, leg liquidity, slippage assumptions, authorized chain, historical chain. |
| Butterfly | Three-strike same-expiration structure, bid/ask/mid/last for all legs, IV surface, Greeks, OI, volume. | No product claim. | Yes. | Observation-only. | Full strike coverage, multi-leg pricing, IV surface, liquidity, historical chain. |
| Iron condor | Four-leg same-expiration structure, call/put spreads, bid/ask/mid/last, IV surface, Greeks, OI, volume, margin/risk assumptions. | No product claim. | Yes. | Observation-only; no margin or suitability claim. | Full chain coverage, multi-leg liquidity, margin context, historical chain, rights. |
| Covered call | Current share position, lot/holding data, call chain, bid/ask/mid/last, OI, volume, IV, Greeks, dividend/corporate-action context. | No product claim; portfolio-linked analysis is not authorized here. | Yes for historical evaluation. | Observation-only only after a separate portfolio read-only safety review. | Portfolio lineage, broker/account boundary, chain rights, assignment/dividend assumptions. |
| Protective put | Current share position, put chain, bid/ask/mid/last, OI, volume, IV, Greeks, dividend/corporate-action context. | No product claim; portfolio-linked analysis is not authorized here. | Yes for historical evaluation. | Observation-only only after a separate portfolio read-only safety review. | Portfolio lineage, chain rights, hedge cost methodology, historical chain. |
| GEX | Chain side/strike/expiration, gamma, OI, multiplier, spot reference, deliverable handling, sign convention, aggregation window. | No. | Historical chain optional for current observation, required for backtest or stability claims. | Blocked; later observation-only after market-structure gates. | Gamma/OI/multiplier coverage, methodology, entitlement, redisplay, decision-use rights. |
| Gamma flip | GEX by strike/spot interval, interpolation or bucketing method, spot reference, coverage thresholds. | No. | Historical chain optional for current observation, required for reliability claims. | Blocked; later observation-only after market-structure gates. | GEX methodology, spot freshness, strike coverage, confidence caps, rights. |
| Vanna | Full Greeks or model inputs, IV surface, spot, time to expiration, rate/dividend assumptions, methodology/version. | No. | Yes for stability, sensitivity, or backtest claims. | Blocked; later observation-only after methodology and rights gates. | IV surface, model assumptions, Greeks coverage, historical chain, methodology approval. |
| Charm | Delta time decay inputs, Greeks/model inputs, IV surface, time to expiration, rate/dividend assumptions, methodology/version. | No. | Yes for stability, sensitivity, or backtest claims. | Blocked; later observation-only after methodology and rights gates. | Time-decay model, IV/Greeks, expiration/freshness, historical chain, methodology approval. |
| Zero-DTE | Same-day expirations, intraday chain freshness, bid/ask/mid/last, IV, Greeks, OI/volume, underlying spot, market-session rules. | No. | Yes for historical zero-DTE evaluation. | Blocked; observation-only only after strict freshness and rights gates. | Intraday freshness, latency/delay, same-day expiration coverage, slippage/quote quality, rights. |
| Dealer positioning | Provider-supplied positioning data or explicit assumption model, GEX/vanna/charm inputs, sign convention, participant-positioning assumption. | No. | Yes for validation or historical claims. | Blocked; later assumption-labeled observation only. | No dealer inventory source, missing rights, sign/positioning assumptions, methodology approval. |

## 5. Provider candidate evaluation template

Do not use this table to record current pricing or commercial terms unless a
reviewed contract or approved procurement artifact exists. Unknown means
unknown; do not infer terms from marketing pages.

| Provider/source class | Data fields | Freshness | History depth | Rights/redisplay | Storage rights | Expected integration complexity | Surfaces unlocked | Score-authority eligibility | Open questions |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OPRA / exchange-licensed vendor category | Chain, quotes, IV, Greeks, OI, volume, expirations, strikes, historical chains, corporate-action/deliverable data. | Live or delayed depending entitlement. | Vendor-dependent; must be contract-proven. | Must be explicitly reviewed for app display and derived analytics. | Must be contract-proven for normalized snapshots and audit replay. | High. Procurement, entitlement, field mapping, and storage policy required. | Options chain, Strategy Lab, IV rank, historical strategy backtest, GEX/vanna/charm after methodology gates. | Possible only after full proof bundle and internal policy approval. | Which fields are licensed, what delay applies, what can be stored, what can be shown, and what derived outputs are allowed? |
| Options analytics vendor category | IV surface, Greeks, OI, volume, chain history, historical IV, derived analytics. | Vendor-dependent. | Often the key differentiator; must be contract-proven. | Must cover user display and derived analytics. | Must cover historical snapshots and derived metrics. | Medium-high. Strong field mapping but strict rights review. | IV rank, Greeks quality, strategy analytics, historical options research, market structure after gates. | Possible only after methodology and rights approval. | Are Greeks provider-computed, what methodology is documented, and are redisplay/storage rights sufficient? |
| Broad market-data vendor with options endpoints | Chain, quotes, reference, corporate actions, maybe IV/Greeks/OI/history. | Plan-dependent. | Plan-dependent. | Must include options-specific exchange and redisplay rights. | Must be separately reviewed. | Medium. API ergonomics may be good, but option-specific gaps must be sampled. | Chain readiness, quote/field coverage, possibly historical chain if entitled. | Not eligible until field, rights, and history depth are proven. | Which plan includes OPRA-equivalent fields, Greeks, OI, historical chains, and display rights? |
| Broker or brokerage-aligned API | Current chain, quotes, sometimes Greeks, account-bound entitlements. | Account/subscription-dependent. | Often limited or pacing-constrained. | High risk for shared app redisplay; account-bound data may be personal-use only. | Usually unclear for shared storage; must be reviewed. | Medium-high. Sessions, account permissions, redaction, and entitlement checks are sensitive. | Narrow private research or user-owned overlay only after safety review. | Not eligible for shared score authority without app-level rights. | Can account-bound data be shown to other users or stored? Are subscriptions per user or app-wide? |
| Public/unofficial fallback source | Exploratory chain fields if available. | Unstable or unclear. | Inconsistent. | Not sufficient for public app rights. | Not sufficient for durable evidence. | Low technically, high product/legal risk. | Local development and observation-only fixtures. | Not eligible. | How is the source licensed, stable, and auditable? Usually it is not enough. |
| Existing fixture/dry-run/adapter-contract path | Contract-shaped chain, IV, Greeks, OI, volume, quotes for deterministic tests. | Synthetic or dry-run only. | Fixture-only. | Internal test use only. | Internal test artifact only. | Low. Already present for contract tests. | Regression tests, demos, fail-closed gate proof. | Not eligible. | None for authority; use only as non-authoritative proof of shape and safety. |

## 6. Recommended next implementation gates

1. Provider selection gate: compare provider/source classes using the template
   above, with field coverage, rights, freshness, history, storage, and
   integration risk documented before any adapter change.
2. Entitlement proof gate: attach sanitized OPRA/equivalent, vendor terms,
   redisplay, storage, historical-data, and personal-use vs public-beta evidence.
3. Local probe gate: run an opt-in, sanitized, non-secret, non-default probe for
   one bounded symbol only after entitlement review; capture field coverage,
   timestamps, delay class, missing fields, and raw-payload redaction proof.
4. Readiness artifact gate: create a reviewed readiness artifact that maps probe
   evidence to chain, IV, Greeks, OI, volume, quote, expiration, strike,
   freshness, and rights blockers.
5. Strategy analyzer UI gate: only after authorized chain evidence exists, scope
   UI work to observation-first strategy analysis with no broker/order/portfolio
   mutation and no strategy advice.
6. Historical strategy backtest gate: require point-in-time historical options
   chains, adjusted underlying history, corporate-action/deliverable handling,
   fees/slippage assumptions, and rights to store/replay data before showing
   historical results.
7. GEX/vanna/charm model-input gate: approve methodology IDs, formulas, units,
   sign/positioning assumptions, confidence caps, and missing-evidence codes
   before any DTO/API/UI implementation.
8. Private beta evidence gate: before any beta claim, archive sanitized evidence
   for entitlement, coverage, freshness, no-advice wording, raw-provider
   suppression, fail-closed missing fields, and demo/sample isolation.

## 7. Safety constraints

- Model-implied probability is an assumption-based estimate. It is not a
  promised win rate and must not be displayed as real-world certainty.
- Historical win rate or historical strategy performance cannot be shown without
  authorized historical option-chain data, adjusted underlying history,
  point-in-time replay rules, and storage/replay rights.
- No strategy, score, rank, label, chain observation, payoff example, or
  market-structure metric may be presented as personalized advice or an action
  instruction.
- Missing chain fields must fail closed. Missing bid/ask/last, IV, Greeks,
  open interest, volume, expiration/strike coverage, underlying freshness,
  rights, or methodology proof must block score-authoritative use.
- Demo, sample, fixture, stub, dry-run, fallback, or adapter-contract data must
  remain observation-only and cannot be promoted by copy, completeness, or
  provider self-claims.
- Provider/cache/runtime details, raw payloads, request IDs, trace IDs,
  credentials, URLs, account identifiers, and entitlement internals must stay out
  of consumer-facing outputs and support artifacts unless separately sanitized
  for operator-only review.
