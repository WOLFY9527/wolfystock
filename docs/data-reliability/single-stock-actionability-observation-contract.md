# Single-Stock Actionability Observation Contract

Status: docs-only product boundary. No runtime implementation is approved.

Date: 2026-06-07

Task anchor: T-1159 defines the safe single-stock actionability boundary before
any frontend report/export guard, backend authority projection, provider
runtime, API/schema, or evidence wiring work.

This document is inert. It does not change backend/provider/cache/runtime/auth
behavior, API or stored contracts, frontend report/export rendering, scoring,
ranking, prompts, or source authority. Future implementation tasks must treat
this contract as a stop sign and checklist, not as implementation approval.

## Current Product Status

T-1149 found single-stock evidence actionability is **NO-GO** for
decision-useful conclusions, with a current score of `40/100`.

Current approved product status:

- single-stock analysis is observation-only;
- no buy, sell, position-sizing, target, stop-loss, or portfolio action claim is
  product-approved;
- Home may support only bounded "continue researching" or "observe with limits"
  flows;
- report, markdown export, and full drawer surfaces must not promote Home's
  bounded research framing into action, advice, or decision use;
- provider/source authority and right-to-display must not be inferred from
  provider success, freshness, coverage, or source confidence.

Consumer-safe single-stock analysis may help a user understand what is known,
what is missing, what needs more research, and which price regions are relevant
as descriptive context. It must not tell the user what to trade, how much to
trade, where to enter, where to exit, or whether a conclusion is approved for
decision use.

## Forbidden Consumer-Default Labels

The labels below must not appear as consumer-default labels in single-stock
Home, full report drawer, markdown export, share/export output, or default
report text.

Forbidden Chinese labels:

- `投资结论`
- `买入`
- `卖出`
- `理想买点`
- `次级买点`
- `止损`
- `目标价`
- `仓位建议`

Forbidden English labels:

- `holding advice`
- `empty-position advice`
- `Action`
- `Ideal buy`
- `Stop loss`
- `Position sizing`

Forbidden meaning, even when renamed:

- any direct or indirect buy/sell instruction;
- any entry/exit/stop/target/size instruction;
- any "should hold", "should add", "should reduce", or empty-position action;
- any label that makes a price level sound executable by default;
- any wording that presents a generated conclusion as investment advice,
  personalized trading guidance, or decision-grade approval.

If an implementation needs to display historic fields that currently carry these
names, it must first map them into observation-only product language or hide them
from consumer-default surfaces.

## Safe Consumer Wording

Allowed consumer wording must stay bounded to research state, evidence
completeness, descriptive scenarios, and uncertainty.

Preferred wording:

- `研究包完整度`
- `继续跟踪`
- `数据不足`
- `情景参考`
- `风险边界`
- `关键价格区间`

Usage constraints:

- `研究包完整度` may describe whether quote, OHLCV, technical, fundamentals,
  news, sector, and provenance lanes are present enough to keep researching. It
  must not mean decision readiness.
- `继续跟踪` may describe a watch/research continuation state. It must not mean
  hold, buy later, wait for entry, or maintain a position.
- `数据不足` must fail closed. It may explain why no conclusion is available; it
  must not be followed by a synthetic trade plan.
- `情景参考` may describe conditional scenarios. It must not rank scenarios as
  recommended actions.
- `风险边界` may describe uncertainty, volatility, invalidation context, or
  missing evidence. It must not be a stop-loss instruction.
- `关键价格区间` may describe observed historical ranges, support/resistance
  context, volatility bands, or scenario inputs only when the copy makes clear
  that they are descriptive. It must not imply ideal entry, stop, target, or
  order placement.

Safe copy should prefer short product-language statements such as:

- `当前研究包仍不完整，仅支持继续跟踪。`
- `部分数据不足，以下内容仅作情景参考。`
- `关键价格区间用于描述观察背景，不构成交易点位。`
- `风险边界用于说明不确定性，不构成止损或仓位建议。`

## Report And Export Boundary

Home's no-advice framing is the minimum safety boundary for all single-stock
consumer surfaces.

Required invariants:

- Full report drawer, markdown export, copied text, downloaded files, and any
  future share/export path must not bypass Home's observation-only framing.
- Exported markdown must not reintroduce action-like section titles, table
  labels, field names, or summary headings that are blocked from Home.
- Full drawer rendering must not make hidden report fields more actionable than
  the default Home surface.
- Price levels may appear only as descriptive scenario or historical context and
  must not be labeled as entry, stop, target, or sizing instructions.
- Consumer exports must omit raw provenance/provider/debug/internal fields by
  default.

Fields that must stay absent from consumer exports and default report surfaces:

- raw provenance payloads;
- provider identifiers and provider debug fields;
- raw source-confidence metadata;
- raw `reasonCode` or `reasonFamilies`;
- raw `sourceRefId`;
- raw internal field names and backend snake_case contract keys;
- `raw_result`;
- `raw_ai_response`;
- `context_snapshot`;
- raw provider payloads, raw LLM payloads, trace IDs, cache keys, retry/circuit
  states, latency buckets, quota buckets, and maintainer remediation detail.

If future report/export work needs provenance context, it must project a
consumer-safe summary first. The projection must answer what can be shown, to
which audience, and why, without exposing the raw evidence chain.

## Data-Lane Authority

Every single-stock evidence lane must carry its own authority and
right-to-display posture. No lane may inherit authority from another lane.
Right-to-display is a separate posture, not a synonym for source provenance,
freshness, provider success, or source confidence.

| Lane | May describe | Must be decided separately |
| --- | --- | --- |
| Quote | latest observed price, session state, as-of time, delayed/stale/partial state | price display right, freshness proof, live/delayed posture, decision-use authority |
| OHLCV | historical bars, volume, range, split/session context | completeness, corporate-action handling, stale/fallback handling, display right |
| Technicals | derived indicators, trend/volatility context, key regions | input coverage, calculation method, freshness, non-advice label mapping |
| Fundamentals | period metrics, missing fields, source period, accounting context | right-to-display, metric coverage, unit/currency semantics, stale/partial posture |
| News | headlines/summaries, published time, relevance context | licensing/redistribution, source display right, freshness, sentiment/actionability boundary |
| Sector/board | sector, board, peer or market context | taxonomy authority, coverage, provider rights, whether comparison is observation-only |
| Source provenance | bounded source summary after projection | source authority, right-to-display, admin-only fields, consumer-safe copy |

Core non-inference rule:

- a successful provider response cannot grant right-to-display;
- freshness cannot grant decision authority;
- high coverage cannot grant source authority;
- source confidence cannot grant provider capability or licensing clearance;
- provider capability cannot grant display rights or consumer badge eligibility;
- cached availability cannot grant live status, route preference, or decision
  readiness;
- official-looking names or public source labels cannot replace explicit
  authority and right-to-display review.

If any lane lacks explicit source authority, display right, freshness proof, or
consumer-safe projection, that lane must fail closed into unavailable,
insufficient, partial, delayed, or observation-only product language.

## Admin-Only Visibility

Raw diagnostic fields may support operations, audits, and research-support
workflows only when a future task explicitly scopes the audience, gate,
sanitization, and retention policy.

Admin/research-support-only field families include:

- `raw_result`;
- `raw_ai_response`;
- `context_snapshot`;
- source provenance internals;
- provider/debug fields;
- raw source-confidence fields;
- provider capability rows;
- right-to-display review states;
- source authority flags;
- reason codes and source reference IDs;
- raw diagnostic JSON after sanitization;
- operator remediation notes.

Visibility rules:

- these fields must be absent from consumer-default UI and consumer exports;
- admin or research-support access must be gated and explicitly allowed;
- raw payloads must be sanitized before display;
- secrets, credentials, cookies, API keys, raw provider bodies, raw LLM bodies,
  and sensitive stack traces must never be exposed;
- admin visibility does not make the same field safe for consumer display.

## Future Implementation Phases

### M2: Frontend Report/Export No-Advice Guard

Scope: frontend report, full drawer, markdown export, and focused tests/e2e only
when a future task explicitly opens those files.

Required outcomes:

- action-like labels are removed or mapped in `FullDecisionReportDrawer`;
- markdown export cannot reintroduce action-like labels;
- consumer-visible report/export copy preserves observation-only framing;
- raw provider/debug/provenance/internal fields stay absent;
- tests/e2e prove no-advice and consumer-safe report/export behavior.

Still forbidden in M2:

- backend/provider/cache/runtime/auth changes;
- API/schema/stored contract changes;
- authority or right-to-display projection;
- source/provider capability adoption;
- scoring, ranking, prompt, or report-generation semantic changes.

### M3: Explicit Right-To-Display And Authority Projection

Scope: protected-domain task only.

Required outcomes:

- `rightToDisplay` is explicit per audience, surface, and lane;
- authority projection is separate from provider capability, freshness,
  coverage, and source confidence;
- missing or ambiguous authority fails closed;
- provider success, cache hit, freshness, and coverage do not auto-promote any
  lane;
- compatibility and stored-contract impacts are reviewed before API exposure.

M3 must not be bundled into a frontend-only or docs-only task.

### M4: Sector/Board Evidence Wiring

Scope: protected-domain task only.

Required outcomes:

- sector/board taxonomy, provider rights, freshness, coverage, and display
  posture are explicit;
- sector/board context remains observation-only unless a later protected-domain
  approval grants a named stronger use;
- missing sector/board evidence fails closed into consumer-safe product copy;
- no provider/runtime/cache/API/frontend wiring starts without the scoped
  protected-domain checklist.

M4 must not infer sector authority from a provider label, cached classification,
or successful taxonomy response.

## Acceptance Checklist For Future M2

M2 is not accepted unless all items below are true:

- `FullDecisionReportDrawer` contains no action-like labels in consumer-default
  view.
- Markdown export contains no action-like labels.
- Report/export text contains no buy/sell/position-sizing/target/stop-loss
  implication.
- Price-region language is descriptive only and does not imply entry, stop,
  target, or sizing.
- Raw provider/debug/provenance fields do not leak.
- Raw `reasonCode`, `sourceRefId`, `raw_result`, `raw_ai_response`,
  `context_snapshot`, backend snake_case field names, and internal diagnostics
  are absent from consumer exports.
- Tests prove no-advice report/export behavior.
- E2E or route-level coverage proves consumer-safe full drawer and markdown
  export behavior.
- No backend/provider/cache/runtime/auth/API/schema/stored-contract files are
  changed in the M2 task.

## Explicit Non-Approvals

This contract does not approve:

- source code changes;
- tests that alter runtime semantics;
- frontend implementation;
- report/export implementation;
- API or schema changes;
- provider additions;
- provider routing/order/fallback/deadline/cache changes;
- MarketCache TTL/SWR/cold-start behavior changes;
- authority/right-to-display inference;
- scoring/ranking/filtering/selection changes;
- prompt or LLM routing changes;
- admin visibility without gating and sanitization;
- consumer source/freshness/provider badges.

Until M2/M3/M4 are separately scoped and validated, single-stock actionability
must remain observation-only with Home-limited "continue researching" or
"observe with limits" framing.
