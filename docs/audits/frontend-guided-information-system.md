# WolfyStock Guided Information System

Date: 2026-05-09
Branch: `main`
Scope: shared frontend glossary/help infrastructure only. No production page
integration, backend API, provider, scanner, options, backtest, portfolio,
admin runtime, global shell, launch acceptance, or release scan behavior changed.

## Purpose

WolfyStock has professional market, options, portfolio, backtest, data-provider,
and operator concepts that can be unfamiliar to new users. The guided
information system gives these terms one consistent explanation pattern without
adding paragraphs to every page.

Use the shared registry in `apps/dsa-web/src/data/glossaryTerms.ts` and the
shared components in `apps/dsa-web/src/components/help/` when a page needs a
compact explanation.

## Component Rules

- `GlossaryTerm` is the default for known registry terms. Use it around visible
  labels such as `最大回撤`, `IV`, `数据可信度`, or `熔断`.
- `TermTooltip` is for one-off local terms that are not yet in the registry.
  Prefer adding repeated product terms to the registry instead of copying text.
- `HelpHint` is for compact icon-only help beside a field label, metric title,
  table heading, or operator status. The icon must not be the only visible
  label for the surrounding control.
- Tooltips explain terminology only. They must not carry workflow steps,
  warnings that block completion, raw diagnostics, or long policy copy.

## Tooltip vs Disclosure vs Inline Helper

Use a tooltip when:

- the term is visible and short;
- the user needs a definition, not a decision;
- the explanation fits in two concise layers: beginner meaning and professional
  note;
- losing the tooltip content does not prevent task completion.

Use disclosure when:

- the content affects interpretation of a result;
- multiple fields or assumptions need to be read together;
- the explanation includes raw evidence, provider details, schema details,
  trace data, or operational history;
- the user may need to copy or compare the content.

Use inline helper text when:

- the user needs the information before choosing an input;
- the text is critical to form validation, safety framing, or permission
  boundaries;
- the route would be misleading without the message always visible.

## Density Rules

- Keep visible glossary triggers to at most 5 per desktop viewport.
- Keep visible glossary triggers to at most 3 per mobile viewport.
- Do not place tooltips on every table cell. Prefer column headings or summary
  labels.
- Do not stack tooltip triggers inside dense button groups.
- If a page needs more than the limit, add a local glossary drawer or disclosure
  after the layout redesign lands.

## Copy Rules

Beginner explanation:

- maximum 90 Chinese characters;
- explain the plain meaning first;
- avoid formulas unless the term is meaningless without one;
- avoid raw provider, schema, stack, model, or debug vocabulary.

Professional note:

- maximum 140 Chinese characters;
- add the relevant analytical口径, assumptions, or interpretation boundary;
- clarify how the concept is normally evaluated;
- keep domain accuracy without turning the tooltip into documentation.

Risk/use caveat:

- optional, maximum 100 Chinese characters;
- state a limitation, not a command;
- avoid personalized conclusions and action language.

Forbidden patterns:

- noisy walls of text;
- raw debug explanations;
- provider payload or schema dumps;
- investment advice or personalized action language;
- buy/sell/order wording such as `买入`, `卖出`, `下单`, `立即交易`, `必买`,
  `稳赚`, `保证收益`, `best contract`, or `AI recommends you buy`;
- native browser `title` as the only explanation.

## Initial Registry Coverage

Categories:

- `market`
- `scanner`
- `options`
- `backtest`
- `portfolio`
- `risk`
- `provider/data`
- `admin/ops`

Initial terms:

- 波动率
- IV
- Delta
- Theta
- Gamma
- OI
- 成交量
- 回撤
- 最大回撤
- 夏普比率
- 胜率
- 盈亏比
- 回测
- 样本外
- 数据延迟
- fallback
- provider
- cache
- 熔断
- SLA
- 曝险
- 可用现金
- 持仓
- 手工记账
- 观察信号
- 证据置信度
- 数据可信度

## Rollout Plan After Page Redesigns Land

Portfolio:

- Add `GlossaryTerm` to `曝险`, `可用现金`, `持仓`, and `手工记账`.
- Prefer headings or metric labels, not every value row.
- Keep manual-record language ledger-only and avoid order/execution wording.

Scanner:

- Add `观察信号`, `证据置信度`, `数据可信度`, `成交量`, and `波动率`.
- Put explanations on candidate summary labels and evidence headings.
- Keep provider/debug details inside secondary disclosures.

Options:

- Add `IV`, `Delta`, `Theta`, `Gamma`, `OI`, `波动率`, and `成交量`.
- Use `HelpHint` beside chain-column headings only when the column remains
  visible after the layout pass.
- Keep explanations analytical and avoid strategy instructions.

Backtest:

- Add `回测`, `样本外`, `最大回撤`, `夏普比率`, `胜率`, and `盈亏比`.
- Prefer KPI label tooltips and a separate evidence disclosure for assumptions,
  fees, slippage, trace, and ledger details.

Admin/Ops:

- Add `provider`, `cache`, `fallback`, `数据延迟`, `熔断`, `SLA`, and
  `数据可信度`.
- Use terms in operator summaries first; raw route/category/bucket/schema
  language should remain behind details.

Market:

- Add `波动率`, `成交量`, `数据延迟`, `cache`, `fallback`, and `数据可信度`.
- Use glossary triggers on freshness and market-state labels, not on every
  quote row.
