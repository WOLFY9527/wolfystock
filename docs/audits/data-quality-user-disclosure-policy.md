# Data Quality User Disclosure Policy

Date: 2026-05-07
Mode: docs-only product safety policy. No runtime code, tests, frontend,
schema, Options, Data Pipeline, scanner, backtest, portfolio, cost/quota,
provider circuit, auth/security, broker, or order behavior changed.

## 1. Purpose

This policy defines how WolfyStock should disclose data quality to users before
showing decision-like labels, scores, rankings, backtest summaries, portfolio
risk views, or Options Decision Engine outputs.

The goal is to prevent users from mistaking incomplete, stale, delayed,
fallback, synthetic, or demo data for decision-grade market evidence.

## 2. Data Quality Tiers

WolfyStock user-facing surfaces should use the following tier policy.

| Tier | Meaning | Maximum product posture |
| --- | --- | --- |
| `decision_grade` | Required data is present, fresh enough for the surface, source is disclosed, and no disqualifying fallback/synthetic/demo state is present. | May show cautious conditional labels such as `有条件可交易` when risk checks also pass. |
| `analysis_grade` | Core analysis data is usable, but one or more important fields are missing, stale, delayed, or lower confidence. | Analytical summary only; no high-confidence tradeable label. |
| `partial` | Some useful data exists, but required or important fields are incomplete enough to materially affect interpretation. | `仅观察` or `不建议`; explain missing data. |
| `insufficient` | Required data is unavailable, invalid, contradictory, or too stale for the requested decision. | `数据不足，禁止判断`. |
| `demo_only` | Data is fixture, synthetic, fallback-only, demo, mocked, or otherwise not a live decision source. | Demo analysis only; no tradeable label. |

Tier names are product policy labels. Runtime schemas may use existing field
names until a separately reviewed schema change is approved.

## 3. Required Source And Freshness Disclosure

Any covered surface that shows a decision-like label, score, rank, scenario, or
risk summary must disclose:

- `asOf`: when the displayed data was observed, generated, or last updated.
- `source`: normalized provider/source label, not raw provider payload.
- `freshness`: fresh, delayed, stale, partial, unknown, or an equivalent
  bounded status.
- Fallback, synthetic, fixture, demo, mocked, or delayed status when present.

Disclosure rules:

- Do not hide data-quality status in developer-only panels when a decision-like
  label is visible.
- Do not expose raw provider JSON, request URLs, query strings, credentials,
  account identifiers, raw prompts, raw LLM responses, cookies, tokens, or stack
  traces.
- If multiple sources contribute to one output, disclose the primary source and
  the most important limiting source.
- If freshness differs by component, show the limiting stale component rather
  than a misleading aggregate "fresh" label.

## 4. Confidence Caps

The following states must cap confidence and downgrade user-facing labels.

### Required Data Missing

If required quote, price history, option chain, portfolio holding, or backtest
input data is missing:

- Maximum tier: `insufficient`.
- Required copy: `数据不足，禁止判断`.
- Do not show tradeable or high-confidence labels.

### Fundamentals Missing

If fundamentals are material to the surface but unavailable:

- Maximum tier: `analysis_grade`.
- Required copy should explain that valuation or business-quality analysis is
  incomplete.
- Scanner and analysis reports may remain analytical, but confidence must be
  capped.

### Stale Quote

If the quote is stale for the surface:

- Maximum tier: `partial` unless the surface is explicitly historical only.
- Required copy should show quote time and stale status.
- Options, scanner, analysis, and portfolio views must not show
  high-confidence tradeable labels from stale quotes.

### Missing Greeks / IV / OI For Options

If Options outputs lack Greeks, implied volatility, open interest, volume,
bid/ask, multiplier, expiration, or underlying freshness:

- Maximum tier: `partial` or `insufficient`, depending on missing-field
  severity.
- Required copy should name the missing fields.
- Do not fabricate Greeks, IV, bid/ask, OI, volume, or liquidity values.
- Do not show high-confidence tradeable labels.

### News / Sentiment Missing

If news or sentiment enrichment is missing:

- Maximum tier: `analysis_grade` for surfaces that can still operate from
  required market/fundamental data.
- Required copy should say that event and sentiment context is incomplete.
- Missing optional enrichment must not block basic analysis by itself, but it
  must cap confidence where event risk matters.

### Synthetic / Fallback / Demo / Delayed Data

If data is synthetic, fallback-only, fixture, demo, mocked, or delayed:

- Synthetic, fallback, fixture, demo, or mocked data maximum tier: `demo_only`.
- Delayed data maximum tier: `analysis_grade` unless a future reviewed policy
  explicitly grants a stronger tier.
- Required copy must make the limitation visible near the decision-like output.
- No high-confidence tradeable label is allowed.

## 5. UI Copy Guidelines In Chinese

Preferred copy patterns:

- `数据不足，禁止判断：缺少必要行情或关键字段。`
- `仅观察：当前数据为延迟或部分数据，不能作为交易依据。`
- `不建议：风险或数据质量未满足当前策略条件。`
- `有条件可交易：仅表示在当前假设、数据质量和风险约束下具备分析价值，不构成投资建议。`
- `高风险，仅限小仓验证：该标签只描述风险等级，不代表收益保证或买入建议。`
- `数据来源：{source}，截至：{asOf}，新鲜度：{freshness}。`
- `当前使用演示/合成/回退数据，仅用于功能体验，不可作为交易判断。`
- `缺少 IV / Greeks / OI / bid-ask 等关键期权字段，已下调置信度。`
- `回测结果基于历史或模拟假设，不代表未来收益。`
- `组合风险视图用于展示敞口和波动风险，不是调仓指令。`

Copy rules:

- Use Chinese user-facing labels by default.
- Put data-quality limitations close to the affected score, rank, or label.
- Avoid promotional, urgent, or certainty-based language.
- Avoid hiding material limitations behind tooltips only.
- Do not translate "decision support" into wording that sounds like a direct
  trading instruction.

## 6. Surface Requirements

### Options Lab

- Show source, `asOf`, freshness, delayed/fallback/synthetic/demo status, and
  missing Greeks/IV/OI/bid-ask warnings near contract scores or strategy
  summaries.
- Fixture and synthetic chains are always `demo_only`.
- Delayed option chains cannot produce high-confidence tradeable labels under
  current policy.

### Scanner / Analysis Report

- Show source/freshness for price, fundamentals, news, sentiment, and any major
  score inputs when available.
- Cap confidence if fundamentals, quote freshness, or optional enrichment is
  missing.
- Do not let score rank alone imply a trade recommendation.

### Backtest Report

- Show sample period, generated time, data source, assumptions, and major
  missing inputs where applicable.
- Clearly separate historical/simulated performance from current trade
  readiness.
- Do not display order CTAs from backtest results.

### Portfolio Risk View

- Show holdings source, quote source, FX source, sync/as-of timestamps, stale
  status, and manual/demo/fallback position state when relevant.
- Cap confidence when holdings, quotes, or FX are stale or incomplete.
- Risk labels must describe exposure, not prescribe trades.

## 7. Future Audit Checklist

Future UI, API, or report changes touching covered surfaces should pass this
checklist:

- [ ] Every decision-like label has visible `asOf`, source, and freshness
  disclosure.
- [ ] Fallback, synthetic, fixture, demo, mocked, delayed, partial, and stale
  states are visible near the affected output.
- [ ] Required-data-missing states display `数据不足，禁止判断`.
- [ ] Demo/synthetic/fallback data cannot produce a tradeable label.
- [ ] Delayed data cannot produce a high-confidence tradeable label under
  current policy.
- [ ] Missing fundamentals, stale quotes, missing options Greeks/IV/OI, and
  missing news/sentiment cap confidence as documented.
- [ ] No raw provider payloads, raw request URLs, credentials, account ids,
  cookies, tokens, raw prompts, raw LLM responses, or stack traces are exposed.
- [ ] No broker/order execution CTA is present.
- [ ] Chinese copy avoids certainty, urgency, guaranteed-return, or personalized
  advice posture.
- [ ] Backtest and portfolio labels remain analytical and assumption-bound.

## 8. Validation For This Docs-Only Policy

Required validation:

```bash
git diff -- docs/audits/trading-no-advice-product-policy.md docs/audits/data-quality-user-disclosure-policy.md docs/CHANGELOG.md
git diff --check -- docs/audits/trading-no-advice-product-policy.md docs/audits/data-quality-user-disclosure-policy.md docs/CHANGELOG.md
```

No `ci_gate` is required for this docs-only policy batch.
