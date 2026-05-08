# WolfyStock Frontend Information Density and Guided Disclosure Standard

Date: 2026-05-09
Branch baseline: `main`
Mode: frontend docs and standards only. This standard governs future page
redesign tasks and does not approve app-code, backend, launch-acceptance, test,
provider, scanner, portfolio, backtest, broker, auth, or runtime changes by
itself.

## Purpose

WolfyStock should feel like a professional quant terminal, but launch-facing
pages must not ask users to decode every implementation detail at once. The
default page should answer a clear product question, show enough evidence to be
trusted, and keep raw diagnostics available without making them primary.

Use this standard together with:

- `CODEX_FRONTEND_DESIGN_CONSTITUTION.md`
- `docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md`
- route-specific launch audits under `docs/audits/`

This document is not a copy-only checklist. Future redesign tasks that cite it
must change layout, hierarchy, and information architecture where needed.

## 1. Page Hierarchy Model

Every launch-facing page must be organized in this order unless the task gives a
strong route-specific reason to differ.

1. **Page intent**
   - One short page title and one compact description of what the page helps the
     user understand.
   - The intent must be user-facing, not implementation-facing. For example,
     prefer `市场温度` over provider/cache readiness as the title-level concept.

2. **Current state**
   - The first meaningful status in the viewport: what is known now, what is
     unavailable, and whether the state is live, cached, partial, or waiting.
   - Do not make stale, fallback, mock, or partial data look fully healthy.

3. **Primary user question**
   - The main question the page answers, written in product language.
   - Examples: `今天市场状态是否值得继续观察?`, `哪些候选值得进一步研究?`,
     `组合风险集中在哪里?`, `这次回测结论是否有足够证据?`

4. **Recommended observation / next safe step**
   - A non-trading, non-ordering next step such as observe, review assumptions,
     inspect evidence, refine filters, compare scenarios, export report, or
     wait for more data.
   - Do not use buy/sell/order language as a default CTA.

5. **Evidence summary**
   - The smallest set of metrics, states, or findings required to justify the
     current state and safe next step.
   - Evidence should be grouped by meaning, not source system.

6. **Details / diagnostics**
   - Raw fields, provider names, cache keys, fallback reasons, schema terms,
     trace logs, assumptions, and debug panels belong here.
   - Details are collapsed by default unless the page is an admin/operator page
     whose primary task is diagnostics.

## 2. Information Density Budgets

These are default launch-surface budgets. Exceeding them requires explicit
justification in the implementation report and browser evidence that the first
viewport remains scannable.

| Surface | Default budget |
| --- | --- |
| Visible summary cards in first desktop viewport | 3 to 5 cards maximum |
| Visible summary cards in first mobile viewport | 1 to 3 cards maximum |
| Chips per card | 3 maximum; 4 only for dense professional evidence cards |
| Default visible metric groups | 3 maximum before the first disclosure |
| Primary buttons in first viewport | 1 primary action, plus up to 2 secondary actions |
| Warning strips | 1 consolidated warning band before details |
| Tables before summary | Not allowed, except admin logs with an operator summary above |

### Collapse Details When

- a panel contains provider, cache, route, schema, raw payload, fixture, mock,
  fallback, trace, ledger, execution assumption, or debug vocabulary;
- the content is useful for audit but not required to answer the primary user
  question;
- more than three metric groups compete with the page's primary state;
- a table is wider than the core question it supports;
- mobile users would need to pass controls or diagnostics before reaching the
  main result.

### Tooltip vs Disclosure vs Drilldown

- **Tooltip**: Use for one term, abbreviation, or short state explanation.
  Tooltips must be reachable on hover and focus. Do not put critical risk
  information only in a tooltip.
- **Disclosure**: Use for secondary evidence, assumptions, data freshness,
  methodology notes, and professional explanation that should stay on the same
  page.
- **Drilldown**: Use when the user is intentionally switching tasks, such as
  opening a candidate inspector, full report, run history, admin raw logs, or
  route diagnostics.

## 3. Guided Disclosure Levels

Every complex page should map content into these four levels.

### Level 0: One-Line Status

- One sentence or compact status band.
- Answers: `现在能不能信?` and `下一步是什么?`
- Examples: `市场数据部分可用，先观察广度和风险分布。`,
  `候选结果已生成，建议先复核入选原因。`

### Level 1: Beginner Explanation

- Plain-language explanation of unfamiliar terms, data gaps, risk, and
  uncertainty.
- Uses examples to clarify meaning, but never tells the user what to trade.
- Suitable for first-run and launch-facing default UI.

### Level 2: Professional Evidence

- Metrics, assumptions, ratios, time windows, confidence, source freshness, and
  comparative evidence.
- May use domain abbreviations such as RSI, MACD, IV, CAGR, Sharpe, Max DD, and
  FX after providing accessible context.

### Level 3: Raw / Developer Diagnostics

- Provider routes, cache keys, raw payload shape, schema fields, fallback
  branches, trace IDs, test fixtures, dry-run output, and internal flags.
- Collapsed by default for all user-facing pages.
- Admin/Ops pages may surface more Level 3 content, but must still start with
  operator-readable state and impact.

## 4. Beginner-Friendly UX Rules

- Every professional term that can affect interpretation needs a hover/focus
  explanation, inline helper, or adjacent disclosure.
- Explanations should use examples such as `例如：成交量放大但价格没有突破，说明信号仍需确认。`
- Examples must explain analysis context only. They must not tell the user to
  buy, sell, open, close, or size a position.
- Risk and uncertainty must be visible near the conclusion, not buried in raw
  data.
- Never hide uncertainty behind green badges. Green can indicate availability
  or completion only when the limitation text remains visible.
- Do not label fallback, mock, partial, stale, or unavailable data as live.
- Avoid raw English status words in Chinese routes unless they are accepted
  market abbreviations or provider/product names.
- Dense financial pages should still have a first-run path: status, meaning,
  evidence, details.

## 5. Domain-Specific Rules

### Market Overview

- First viewport answers: `当前市场温度是否可用于观察?`
- Show a market state, data readiness, and the top risk/rotation clue before
  sector tables or provider details.
- Collapse cache, fallback, backup, and payload quality detail into data
  readiness disclosure.
- Partial data should render a degraded but readable state, never a blank page.

### Scanner

- First viewport answers: `哪些候选值得进一步研究，为什么?`
- Candidate shortlist comes before scan configuration, history, and diagnostics.
- Each candidate should expose one primary safe action such as `查看依据` or
  `加入观察`, plus `更多`.
- Candidate explanations must include why it was selected, main risk, and next
  safe observation step.
- Provider, mock, generated/failed candidate counts, and developer diagnostics
  are Level 3 by default.

### Watchlist

- First viewport answers: `我关注的标的现在有什么变化?`
- Rows or grouped symbols are the main surface; batch operations are secondary.
- Filter controls should be compact and not push the watchlist below the fold on
  mobile.
- Intelligence chips must explain their meaning and remain limited to the most
  useful states.

### Portfolio

- First viewport answers: `组合风险、敞口、收益和数据可信度在哪里?`
- Holdings, P&L, exposure, FX readiness, and read-only sync state come before
  manual record forms.
- Manual mutations must be framed as ledger/accounting records, not broker
  order execution.
- Words such as `买入`, `卖出`, `提交交易`, `下单`, and `立即交易` must not appear
  in default launch content unless explicitly safety-reviewed.

### Options Lab

- First viewport answers: `这个期权情景是否有足够数据用于研究?`
- Safety/read-only/no-advice framing comes before chains, strategy controls, or
  ranking tables.
- Rename execution-flavored labels into scenario/readiness language.
- Option chain tables, provider/mock terms, and raw Greeks diagnostics are
  collapsed until assumptions are set.

### Backtest

- First viewport answers: `这次历史检验结论是否可信?`
- Report summary, key performance/risk metrics, and assumptions status come
  before export, rerun, trace, ledger, and raw data quality controls.
- Execution assumptions and data quality are professional evidence when
  summarized, raw diagnostics when expanded.
- No broker/order implication should appear in result actions.

### AI Chat / Report

- First viewport answers: `我能问什么，系统会如何限定答案?`
- Prompt starters must be analysis and risk framing, not opening positions,
  entry points, stop loss, target price, or trade execution.
- Report decision language must be analytical, conditional, and no-advice.
- Raw prompts, provider/model routing, and LLM traces stay collapsed.

### Admin / Ops

- First viewport answers: `系统现在能不能安全运行，哪里需要人工处理?`
- Operator summaries come before provider/cache/TTL/schema/bucket/route
  details.
- Raw logs, cleanup, destructive maintenance, dry-run responses, and raw
  diagnostics are secondary and should require explicit expansion or
  confirmation.
- Admin pages may be denser than user pages, but they still need state, impact,
  recommended operator action, evidence, then details.

## 6. Screenshot Anti-Patterns to Reject

Reject future redesigns that preserve these visible patterns:

- scattered tiny cards with no dominant page story;
- giant empty black bands before meaningful content;
- same-weight grids where every panel looks equally important;
- provider, cache, fallback, schema, fixture, or debug terms in default user UI;
- dense form walls before state, evidence, or result summary;
- tables before summaries;
- stacked warning strips without severity or hierarchy;
- card shadows, borders, or glow effects that visually overlap and blur panel
  ownership;
- controls that push the main artifact below the mobile first meaningful
  viewport;
- primary UI that requires knowing backend concepts to understand the page.

## 7. Acceptance Checklist for Future Page Redesigns

Every future Codex page redesign that cites this standard must report:

- first desktop viewport content order, from top to bottom;
- first mobile viewport meaningful content order, from top to bottom;
- visible summary card count in the first desktop and mobile viewport;
- whether details, diagnostics, provider/cache/raw fields, and tables are
  collapsed by default;
- which professional terms received tooltip, helper text, disclosure, or
  drilldown treatment;
- confirmation there is no buy/sell/order/trade CTA unless explicitly
  requested and safety-reviewed;
- confirmation raw/debug/provider/cache terms are not primary user-facing
  content;
- confirmation no horizontal overflow at desktop and mobile viewports;
- route-specific browser evidence or an explicit blocker if browser proof was
  not possible.

## 8. Prompt Template Snippets

Use these snippets in future task prompts when redesigning WolfyStock pages.

```text
This must be a layout and information-architecture pass, not a copy-only,
test-only, or screenshot-only pass. Change hierarchy, default disclosures, and
first-viewport content order where needed.
```

```text
Final report must include first desktop viewport content order and first mobile
viewport meaningful content order, plus visible summary card counts.
```

```text
Add beginner guidance for domain terms. Professional terms must have hover/focus
explanations, inline helper text, or secondary disclosure. Do not turn examples
into trading advice.
```

```text
Move provider/cache/debug/raw diagnostics out of the default primary UI. Keep
them available in collapsed details or drilldowns when they are useful evidence.
```

```text
The first viewport must answer: page intent, current state, primary user
question, recommended safe next step, and evidence summary before details.
```

## 9. Review Standard

For future reviews, a page is not launch-ready only because it has no overflow
and passes tests. It must also be understandable in the first meaningful
viewport, explain its domain terms, expose uncertainty honestly, and provide a
safe guided path before raw detail.
