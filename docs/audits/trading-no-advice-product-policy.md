# Trading No-Advice Product Policy

Date: 2026-05-07
Mode: docs-only product safety policy. No runtime code, tests, frontend,
schema, Options, Data Pipeline, scanner, backtest, portfolio, cost/quota,
provider circuit, auth/security, broker, or order behavior changed.

## 1. Purpose

This policy defines user-facing trading decision boundaries for WolfyStock
surfaces that can display scores, rankings, scenarios, or portfolio risk
signals. It applies especially to Options Lab / Options Decision Engine,
scanner and analysis reports, backtest reports, and portfolio risk views.

WolfyStock may provide analytical decision support. It must not present outputs
as personalized investment advice, trading instructions, broker execution
readiness, or order placement.

## 2. Scope

Covered product surfaces:

- Options Lab and Options Decision Engine outputs.
- Scanner scores, rankings, and analysis summaries.
- Standard analysis report scores, labels, and generated commentary.
- Backtest reports, strategy summaries, and performance diagnostics.
- Portfolio risk, exposure, drawdown, and allocation views.

Out of scope for this policy batch:

- Runtime implementation.
- UI or API schema changes.
- Options provider adapters or data pipeline changes.
- Scanner, backtest, portfolio, cost/quota, auth/security, provider circuit,
  broker, or order execution behavior.

## 3. Allowed Language

User-facing labels may use cautious analytical terms that describe data
sufficiency, risk, and conditional observability:

- `数据不足，禁止判断`
- `不建议`
- `仅观察`
- `有条件可交易`
- `高风险，仅限小仓验证`

Allowed phrasing rules:

- Use condition-based wording: "在数据完整且风险约束满足时".
- Tie any positive label to assumptions, data quality, and risk controls.
- Prefer "观察", "分析", "情景", "风险", "约束", "置信度上限" over directive
  trading verbs.
- Explain why a score is capped or downgraded when data is missing, stale,
  synthetic, fallback-only, delayed, or otherwise not decision-grade.

## 4. Forbidden Language

User-facing trading and Options surfaces must not use certainty, guarantee,
personalized-advice, or order-like language such as:

- `必买`
- `稳赚`
- `保证收益`
- `立即交易`
- `best contract`
- `guaranteed`
- `AI recommends you buy`

Also forbidden:

- "guaranteed profit", "risk-free", "sure win", or equivalent wording.
- "buy now", "place order", "submit order", "broker-ready", or equivalent
  order CTA wording.
- Personalized suitability claims such as "适合你买入" unless a separate
  regulated suitability framework is approved.
- Any label that implies a fill price, execution certainty, or broker
  connectivity when no order path is in scope.

## 5. Output Boundaries

All covered outputs must preserve these boundaries:

- Analytical decision support only.
- Not personalized investment advice.
- No implication that WolfyStock is a broker, advisor, execution venue, or
  order router.
- No implication that a score, rank, label, backtest result, or portfolio risk
  view predicts future returns.
- No raw provider payloads, raw LLM prompts, raw LLM responses, credentials,
  account identifiers, cookies, tokens, request URLs, or stack traces in the
  UI or reports.

Any ranking or score is an analytical view under explicit assumptions. It is
not an instruction to trade.

## 6. Required Disclosure Surfaces

### Options Lab

Required visible disclosures:

- Options are high-risk and can expire worthless.
- Outputs are analysis support, not personalized investment advice.
- No broker/order execution is available or implied.
- Data quality, source, freshness, delayed/fallback/synthetic status, and key
  missing fields must be visible before any tradeability-like label is shown.
- Fixture, synthetic, fallback, or demo data must be labeled as not tradeable.

### Scanner / Analysis Report

Required visible disclosures:

- Scanner scores and analysis labels are analytical signals only.
- Scores do not guarantee future price movement or returns.
- Missing fundamentals, stale quotes, missing news/sentiment, or partial data
  must cap confidence and be disclosed.
- Reports must avoid order CTAs and personalized buy/sell instructions.

### Backtest Report

Required visible disclosures:

- Backtest performance is historical or simulated and does not guarantee
  future results.
- Strategy summaries must disclose sample window, assumptions, fees/slippage
  coverage if available, and data completeness limits.
- A backtest pass/fail label must not become an instruction to trade now.
- No broker/order CTA may be attached to backtest results.

### Portfolio Risk View

Required visible disclosures:

- Portfolio risk views describe exposure, concentration, drawdown, allocation,
  and scenario risk; they are not personalized investment advice.
- Risk labels must not imply required trades or automatic rebalancing.
- Broker/account sync status, stale holdings, missing FX, delayed quotes, and
  manual/demo positions must be visible when they affect risk interpretation.
- No order placement or broker mutation is implied by risk output.

## 7. Data-Quality Gating

Tradeability-like labels are gated by data quality:

- Synthetic, fallback, fixture, or demo data cannot produce a tradeable label.
- Delayed data cannot produce a high-confidence tradeable label unless a
  future policy explicitly changes this rule.
- Missing required data must cap output at `数据不足，禁止判断` or `仅观察`
  depending on the surface and severity.
- Options outputs missing Greeks, IV, bid/ask, open interest, volume,
  multiplier, expiration, or underlying quote freshness must be downgraded and
  cannot imply trade readiness.
- Scanner, analysis, backtest, and portfolio labels must disclose stale,
  partial, fallback, delayed, or synthetic data before showing decision-like
  summaries.

Recommended label ceiling by data state:

| Data state | Maximum user-facing posture |
| --- | --- |
| Demo, fixture, synthetic, or fallback-only | `仅观察` |
| Required data missing | `数据不足，禁止判断` |
| Delayed data | `仅观察` or `不建议` |
| Partial important data | `仅观察` |
| Decision-grade data with explicit assumptions | `有条件可交易` |
| Decision-grade data with high risk factors | `高风险，仅限小仓验证` |

## 8. Future UI Test Requirements

Future UI implementation or regression tests for covered surfaces must include:

- Forbidden wording scan for `必买`, `稳赚`, `保证收益`, `立即交易`,
  `best contract`, `guaranteed`, and `AI recommends you buy`.
- No raw provider payload, raw request URL, credentials, account ids, cookies,
  tokens, raw prompts, raw LLM responses, or stack traces in DOM, reports, or
  admin-visible product surfaces.
- Data-quality disclosure is visible where decision-like labels, scores,
  rankings, or risk summaries appear.
- No order CTA, broker execution CTA, order ticket, submit order control,
  broker-ready label, or hidden order affordance.
- Synthetic, fallback, fixture, demo, delayed, stale, and partial data states
  cannot display high-confidence tradeable copy.

## 9. Acceptance Checklist

Before a covered surface can be called public-safe:

- [ ] No forbidden wording is visible or generated.
- [ ] No order or broker execution implication is present.
- [ ] No personalized investment-advice posture is present.
- [ ] Data source, `asOf`, freshness, and fallback/synthetic/delayed status are
  visible where relevant.
- [ ] Data-quality caps prevent tradeable labels for demo, synthetic,
  fallback, stale, delayed, or insufficient data.
- [ ] Raw provider and private payloads are not exposed.
- [ ] Backtest, scanner, analysis, Options, and portfolio copy remain
  analytical and assumption-bound.

## 10. Validation For This Docs-Only Policy

Required validation:

```bash
git diff -- docs/audits/trading-no-advice-product-policy.md docs/audits/data-quality-user-disclosure-policy.md docs/CHANGELOG.md
git diff --check -- docs/audits/trading-no-advice-product-policy.md docs/audits/data-quality-user-disclosure-policy.md docs/CHANGELOG.md
```

No `ci_gate` is required for this docs-only policy batch.
