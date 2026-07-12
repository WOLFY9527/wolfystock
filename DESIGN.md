# WolfyStock Design System & Consumer Frontend Contract

Version: 1.2
Status: Canonical consumer frontend contract
Owner: Consumer Frontend
Audience: Codex, frontend engineers, product engineers, reviewers
Visual reference: `docs/design/reference/wolfystock-impeccable-polish-final.html`

---

## 0. How to use this document

This document defines the durable product, information-architecture, visual, interaction, responsive, accessibility, and page-composition contract for WolfyStock consumer frontend work.

It is not:

- an authorization to modify protected backend semantics;
- a replacement for current code and tests;
- a source of runtime market data;
- a standalone HTML implementation plan;
- a requirement to rebuild every route in one task.

### 0.1 Precedence

Use this order when implementing or reviewing frontend work:

1. current task scope and explicit acceptance criteria;
2. repository safety, truth, protected-domain, and delivery rules in `AGENTS.md`;
3. validated production behavior, contracts, code, and tests;
4. this `DESIGN.md`;
5. the visual composition and interaction intent of the HTML reference.

Task criteria may authorize a protected-domain change only when ownership and validation are explicit. They may not silently weaken security, data truth, fail-closed, source authority, or no-advice contracts.

Where the visual reference conflicts with real routes, localization, auth/RBAC, Product Read Model authority, API ownership, freshness, accessibility, or production data behavior, the real WolfyStock contract wins.

### 0.2 Normative status labels

Sections use these meanings:

| Label | Meaning |
| --- | --- |
| `CURRENT_INVARIANT` | Must remain true in the current product. |
| `MIGRATION_TARGET` | Direction for pages being migrated; not authorization for unrelated rewrites. |
| `VISUAL_REFERENCE` | Visual relationship or composition guidance, not runtime truth. |
| `CONDITIONAL` | Applies only when the route or capability exists and owns the relevant workflow. |
| `DEFERRED` | A future direction that must not be presented as implemented. |

### 0.3 Task-routed reading

Do not read every page contract for a bounded task.

- Shell/navigation: sections 1–8, 10, 13–15.
- Consumer page composition: sections 1–6, 9–12, the relevant page contract, and section 15.
- Shared components: sections 3, 5–12, 14–15.
- Data-state work: sections 2–3, 8, 12, 15.
- Migration cleanup: sections 3, 13–15.

---

# 1. Product direction — `CURRENT_INVARIANT`

WolfyStock is a high-density financial research workbench with a restrained Eastern paper visual language.

The core journey is:

```text
看市场
→ 找候选
→ 看个股
→ 加入持续观察
→ 用扫描 / 回测 / 情景分析做验证
→ 检视真实持仓暴露
```

The product optimizes for:

- organizing evidence;
- understanding market context;
- prioritizing research;
- validating hypotheses;
- tracking uncertainty, freshness, provenance, and risk boundaries.

WolfyStock is not:

- a broker or order-entry terminal;
- a buy/sell signal service;
- an investment-advice product;
- a generic SaaS dashboard;
- an admin diagnostic wall on consumer routes;
- a marketing landing page;
- a black-neon exchange interface;
- a collection of AI-generated cards.

It should feel like:

- an interactive research morning note;
- a dense analyst workbench;
- a calm financial research terminal;
- a product where conclusions trace back to evidence;
- a product where data limitations are honest but do not dominate the page.

---

# 2. Non-negotiable product rules — `CURRENT_INVARIANT`

## 2.1 Conclusion first

Core consumer pages should answer in this order:

```text
1. 当前状态 / 当前观察
2. 为什么
3. 数据是否足够可靠
4. 什么可能推翻当前观察
5. 下一步检查什么
6. 详细证据与限制
```

Do not lead with:

- raw tables;
- backend health;
- provider internals;
- contract versions;
- missing-field walls;
- technical diagnostics;
- repeated disclaimers.

## 2.2 Evidence before confidence theater

Do not invent or cosmetically complete:

- scores;
- confidence;
- candidates;
- factors;
- timestamps;
- chart series;
- conclusions;
- availability;
- freshness;
- provenance.

A visually complete page is invalid if its evidence is fabricated or overstated.

## 2.3 Truth semantics

```text
unavailable != zero
missing != zero
missing != neutral
stale != fresh
delayed != live
proxy != official
unknown != available
client receipt time != evidence asOf
render time != observation time
consumer eligible != score eligible
research evidence != trading advice
```

## 2.4 No-advice boundary

Forbidden consumer wording includes:

```text
买入
卖出
持有
目标价
止损
加仓
减仓
仓位建议
现金权重建议
建议上调仓位
建议降低仓位
```

Preferred patterns:

```text
当前观察
结构仍需确认
风险敏感度较高
下一步检查
等待量能确认
观察是否守住关键区域
证据仍不完整
当前数据支持继续观察，不支持直接行动
```

A compact page-level statement may appear once:

> 研究观察，不构成投资建议。

Do not repeat the same disclaimer in every card.

## 2.5 Consumer and Admin boundary

Consumer surfaces must not expose raw internal language such as:

```text
provider_missing
data_disabled
sourceClass
noExternalCalls
providerCallsEnabled
contractVersion
failClosed
readiness_blocked
cache internals
raw lineage JSON
schema versions
provider routing decisions
```

Map internal states to bounded consumer language, for example:

```text
实时
延迟
部分延迟
历史数据可用
历史样本不足
数据源降级
暂无数据
代理数据
报价延迟
当前证据不足
数据待补
```

Authorized Admin/operator surfaces may expose deeper diagnostics, but must still redact secrets and unsafe payloads.

## 2.6 Show / compact / hide

For optional evidence modules:

```text
3+ meaningful real fields → full module
1–2 meaningful real fields → compact summary
0 meaningful real fields → hide or bounded empty state
```

Do not render giant empty tables, repeated “待补” cells, placeholder dashboards, or fake values for symmetry.

---

# 3. Frontend architecture contract — `CURRENT_INVARIANT`

## 3.1 Keep the existing stack

Production frontend remains inside the current React/Vite application and existing ownership boundaries.

Do not create:

- standalone replacement HTML pages;
- a second router;
- a second auth system;
- a second state mapper;
- a second chart framework;
- a competing UI framework;
- a parallel data authority;
- local hardcoded runtime market arrays.

The HTML reference is a visual north star, not production code.

## 3.2 Preserve validated contracts

Frontend changes must preserve:

- canonical and localized routes;
- deep links, refresh, and browser history;
- session restoration and logout semantics;
- auth gates and RBAC;
- admin-only visibility;
- safe redirects;
- API ownership;
- Product Read Model authority;
- freshness and provenance semantics;
- Watchlist symbol identity;
- Portfolio accounting and preview/confirm boundaries;
- Backtest readiness versus execution/result distinction;
- fail-closed behavior;
- UAT provider isolation;
- no-advice semantics.

## 3.3 Render pipeline

Preferred flow:

```text
API DTO
→ domain / read-model interpretation
→ existing consumer presentation mapping
→ consumer component
→ page composition
```

Avoid:

```text
API DTO
→ each page independently interprets backend enums and readiness
```

Extend existing presentation ownership instead of creating page-local parallel mappings.

## 3.4 Passive-load boundary

Passive load must not trigger:

```text
provider activation
scanner execution
backtest execution
portfolio mutation
watchlist mutation
auth/account mutation
external notification delivery
```

One user action should cause at most one intended state transition.

---

# 4. Information architecture — `CURRENT_INVARIANT` / `MIGRATION_TARGET`

## 4.1 Primary hierarchy

Recommended consumer hierarchy:

```text
首页

市场 ▾
  市场总览
  流动性监测
  板块轮动
  other real market-context surfaces

研究 ▾
  研究雷达
  个股研究
  扫描器

观察列表

验证 ▾
  回测
  情景实验室
  other real hypothesis-validation tools

持仓
```

Admin/operator entry points remain role-gated and visually separated.

This hierarchy is a default, not permission to move routes without auditing the real route inventory and workflow ownership.

## 4.2 Route classification

Classify surfaces before shell changes:

```text
PRIMARY_WORKSPACE
PRIMARY_TASK_DOMAIN
SECONDARY_DOMAIN_TOOL
CONTEXTUAL_RESEARCH_ENTRY
ROLE_GATED_ADMIN_SURFACE
ACCOUNT_UTILITY
LEGACY_OR_DUPLICATE_ENTRY
```

Every meaningful production surface needs at least one discoverable path:

```text
global navigation
or grouped navigation
or clear contextual handoff
```

No canonical route may become an accidental orphan.

## 4.3 Route behavior

Every production route must preserve:

- canonical identity and locale prefix;
- direct address navigation;
- refresh;
- browser back/forward;
- auth/session state;
- meaningful query parameters;
- safe redirect behavior;
- route-aware document title where owned.

Grouped navigation must support keyboard interaction, Escape, visible focus, active child state, active parent state, and non-hover access on tablet/mobile.

---

# 5. Visual direction — `MIGRATION_TARGET` / `VISUAL_REFERENCE`

## 5.1 Creative direction

> A breathing Eastern financial research paper: restrained, dense, analytical, and readable.

Visual keywords:

- paper research;
- restrained technology;
- professional finance;
- calm evidence;
- analytical memo;
- subtle craftsmanship;
- high information density.

Avoid:

- blue-purple fintech gradients;
- black-neon exchange styling;
- heavy glow;
- excessive glassmorphism;
- card walls;
- emoji icon rows;
- icon-per-card decoration;
- marketing heroes;
- generic admin-dashboard composition;
- decorative metrics without analytical purpose.

## 5.2 Canonical token relationships

Token names may adapt to the existing theme system; semantic relationships should remain stable.

```css
:root {
  --paper: #F5F0EB;
  --paper-deep: #E9DFD3;
  --surface: #FBF8F3;
  --surface-soft: rgba(255, 255, 255, .56);

  --ink: #25221D;
  --ink-soft: #3D3831;
  --muted: #746B60;
  --muted-2: #9B9184;

  --line: rgba(54, 48, 40, .16);
  --line-strong: rgba(54, 48, 40, .30);

  --sage: #6B8F71;
  --sage-deep: #365D3D;
  --sage-wash: #DCE7DC;

  --gold: #D4A574;
  --gold-wash: #EFE0C9;
  --blue: #6F8FA1;

  --danger: #A75E55;
  --danger-wash: #F0DCD8;
  --ok: #5D8663;
  --warn: #AA7A3D;

  --shadow: 0 18px 44px rgba(55, 44, 31, .09);
  --shadow-tight: 0 8px 20px rgba(55, 44, 31, .07);

  --radius: 18px;
  --radius-sm: 12px;
  --ease: cubic-bezier(.16, 1, .3, 1);
}
```

Gold is a rare accent for annotations, secondary analytical emphasis, or bounded caution. It is not a large-area background.

Do not reuse one color for unrelated meanings. Brand selection, price direction, availability, delay, warning, and unavailable states need distinct semantics.

## 5.3 Typography

```css
:root {
  --font-display:
    "Noto Serif SC", "Songti SC", "STSong",
    "Iowan Old Style", Georgia, serif;

  --font-body:
    "Inter", -apple-system, BlinkMacSystemFont,
    "Segoe UI", system-ui, sans-serif;

  --font-mono:
    "SFMono-Regular", "JetBrains Mono",
    ui-monospace, Menlo, monospace;
}
```

- Display: page titles, research observations, memo headlines, major section headings.
- Body: navigation, controls, forms, descriptions, table labels.
- Mono/tabular: symbols, prices, percentages, dates, times, metrics, Fig/Plate labels.

Financial numbers should use tabular lining numerals. Do not bundle font files solely to copy the prototype without separate approval.

---

# 6. Layout and surface hierarchy — `MIGRATION_TARGET`

## 6.1 Desktop workbench

```css
.shell {
  width: 100%;
  max-width: 1880px;
  margin: 0 auto;
  padding: 14px 18px 38px;
}
```

Use available horizontal space. Do not default to a narrow SaaS content column.

A 12-column grid is the canonical mental model:

```css
.grid-12 {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 10px;
}
```

Common composition:

- chart + analytical summary;
- parameters + results table;
- queue + explanation panel;
- main trend + compact evidence rail;
- full-width ledger where comparison is primary.

## 6.2 Density

- Panel padding: approximately 13–16px.
- Major gap: approximately 8–10px.
- Local row gap: approximately 6–8px.
- Prefer dividers and rows before nested cards.
- Use internal table/ledger scrolling where appropriate.
- Keep first viewport focused on identity, observation, primary surface, evidence quality, and next action.

Avoid oversized heroes, excessive whitespace, equal-weight card grids, giant empty panels, and repeated containers.

## 6.3 Four-level hierarchy

```text
paper background
→ primary work panel
→ bounded row/card/table/disclosure
→ content and numeric evidence
```

### Panel

Use for primary charts, research memo, scanner/backtest results, scenario maps, and major tables.

### Card

Use only when the block owns meaningful research content. Do not create a card for one label, one icon, or one empty state.

### Analyst Memo / Brief

Preferred hierarchy:

```text
当前观察
→ 为什么
→ 证据可靠性
→ 什么可能推翻它
→ 下一步检查
```

### Research strip

Use for compact queues:

```text
symbol + reason
→ evidence strength
→ data state
→ contextual research action
```

Use a table instead when comparison is the primary task.

---

# 7. Global shell and search — `CURRENT_INVARIANT` / `MIGRATION_TARGET`

## 7.1 Top navigation

The shell should be:

- sticky where appropriate;
- route-aware;
- locale-aware;
- keyboard accessible;
- role-aware;
- compact and research-oriented;
- complete without exposing every route as a first-level item.

Retain account, session, language, and theme behavior where currently supported.

Do not hide meaningful routes behind a non-interactive label or hover-only path.

## 7.2 Global symbol search

Expected flow:

```text
input
→ existing debounced symbol-resolution owner
→ exact / fuzzy result
→ canonical symbol and market identity
→ existing canonical stock route
```

Requirements where search is supported:

- `⌘K` / `Ctrl+K`;
- accessible name;
- keyboard result navigation;
- Escape closes;
- loading and no-results state;
- correct symbol/market handoff;
- no provider live probe merely because search opened.

Never use the prototype's local stock array as production search data.

## 7.3 Menus

Grouped and overflow menus require predictable open/close, `aria-expanded`, visible focus, Escape, outside-click behavior where applicable, active state, role filtering, and responsive equivalent.

Use `更多` only for genuinely secondary surfaces, not as a dumping ground for major workflows.

---

# 8. Data-state presentation — `CURRENT_INVARIANT`

## 8.1 Consumer vocabulary

Preferred labels:

```text
实时
延迟
部分延迟
历史数据可用
历史样本不足
数据源降级
暂无数据
代理数据
研究观察
报价延迟
开盘后复核
需要复查
无候选
```

## 8.2 State authority

Bad:

```tsx
<Badge>实时</Badge>
```

without real state support.

Required flow:

```text
backend/domain readiness and provenance
→ existing consumer mapping
→ state badge / freshness stamp / bounded disclosure
```

## 8.3 Freshness and time

Where materially relevant show:

- state;
- observation/as-of time;
- delayed/stale context;
- family-specific freshness when aggregate time would mislead.

Generated time, render time, client receipt time, and evidence observation time must remain distinct.

## 8.4 Data trust disclosure

Detailed provenance and limitations should be reachable but not dominate the first viewport.

Use compact disclosure, drawer, expandable detail, or bounded ledger depending on task density.

---

# 9. Tables, actions, and charts — `MIGRATION_TARGET` / `CURRENT_INVARIANT`

## 9.1 Tables and ledgers

Use tables when users need comparison, sorting, scanning, or repeated structured evidence.

Requirements:

- semantic table structure;
- accessible headers;
- tabular numeric alignment;
- clear units and currency;
- bounded horizontal scrolling;
- no body-level overflow;
- honest empty/loading/error rows;
- row actions remain contextual and accessible.

On mobile, preserve analytical priority; do not convert every table into unrelated cards when a contained scroll or priority-column view is clearer.

## 9.2 Actions

Actions must communicate intent and state:

- primary action is singular and visually clear;
- passive research actions remain distinct from mutation;
- destructive actions require appropriate confirmation;
- loading/disabled state prevents duplicate transitions;
- focus returns appropriately after drawer/dialog closure;
- copy/export reports success or failure accessibly.

Consumer actions must not use trading-advice language.

## 9.3 Charts

Every chart needs:

- real data ownership;
- explicit metric and unit;
- time range;
- honest missing/stale state;
- readable legend or direct annotation;
- accessible summary;
- responsive containment.

Do not fabricate a series, interpolate rejected gaps, or draw a static decorative financial path.

### Stock chart

Preserve canonical symbol, market, interval, adjustment, freshness, and provenance. Missing history remains missing.

### Market chart

Distinguish official, proxy, delayed, and partial evidence. Do not let proxy breadth or unofficial rows support an institutional-grade headline.

### Backtest chart

Result charts render only from a real executed/stored result. Readiness, no-result, result, compare, and drawdown states remain distinct.

## 9.4 Signature visualization

A radar or signature visual may summarize real multidimensional evidence when:

- dimensions have stable meaning;
- values derive from authoritative existing data;
- missing dimensions remain missing;
- a textual or tabular explanation exists;
- it does not become a hidden recommendation score.

---

# 10. Motion and accessibility — `CURRENT_INVARIANT`

## 10.1 Motion

Motion should clarify hierarchy and state, not decorate.

- respect `prefers-reduced-motion`;
- avoid long entrance sequences;
- do not animate core numbers in a way that delays reading;
- keep loading indicators bounded;
- preserve focus and interaction during transitions.

## 10.2 Accessibility

Required:

- one meaningful page `h1`;
- logical heading order;
- keyboard access to all core workflows;
- visible focus;
- accessible names and states;
- semantic controls instead of clickable divs;
- `aria-live` or status semantics for async feedback where appropriate;
- Escape behavior for dialogs, drawers, menus, and overlays;
- focus restoration after modal surface closure;
- non-color state communication;
- readable contrast;
- table accessibility;
- no hover-only route or evidence access.

---

# 11. Responsive composition — `MIGRATION_TARGET`

Target qualification viewports:

```text
1440x1000
1024x900
768x900
390x844
```

## 11.1 Wide desktop

- use horizontal analytical composition;
- keep primary chart/table and supporting evidence visible together where useful;
- avoid narrow center columns;
- preserve high density without reducing readability.

## 11.2 Tablet

- preserve task priority rather than merely stacking DOM order;
- keep grouped navigation discoverable;
- ensure controls and tables remain usable;
- avoid body overflow.

## 11.3 Mobile

Preferred research sequence:

```text
identity
→ current observation
→ primary analytical surface
→ evidence quality / freshness
→ next checks
→ expandable detail
```

Requirements:

- safe touch targets;
- contained table scrolling;
- readable charts;
- no clipped controls;
- no page-level horizontal escape;
- critical actions remain reachable;
- disclosures and menus remain keyboard/screen-reader usable.

---

# 12. Content voice and common states — `CURRENT_INVARIANT`

## 12.1 Voice

Consumer copy should be:

- analytical;
- bounded;
- calm;
- direct;
- evidence-aware;
- honest about uncertainty.

Avoid marketing superlatives, internal diagnostics, repeated legal walls, filler copy, and implied promises.

## 12.2 Loading

- show what is loading;
- preserve stable shell and known context;
- avoid fake completed content;
- local panel loading should not block the entire application.

## 12.3 Empty

Answer:

```text
what is empty?
why, if known?
what can the user do next?
```

Do not show fake rows or candidates.

## 12.4 Partial / stale

Readable evidence may remain visible when allowed, with explicit state, as-of, scope, and bounded implication.

## 12.5 Error

Use actionable consumer language, not raw API or stack information. Do not promise preserved data unless that is factually true.

## 12.6 Blocked

Explain the user-level blocker without leaking provider, auth, cache, schema, or admin internals. Preserve fail-closed behavior.

---

# 13. Page contracts — `CONDITIONAL` / `CURRENT_INVARIANT`

Each page contract uses one structure:

```text
Purpose
First viewport
Primary surface
Evidence and states
Workflow continuity
Read/mutation boundary
Responsive priority
Validation focus
```

## 13.1 Home

**Purpose**

Provide a bounded first read and a useful research starting point.

**First viewport**

- route identity;
- current market observation or honest inability to conclude;
- prioritized research queue or true empty state;
- freshness/completeness summary;
- next research path.

**Primary surface**

Market context plus research order, not a feature directory.

**Evidence and states**

- use real index/market paths where available;
- preserve guest/auth boundaries;
- no fake ticker, metric, or chart;
- unavailable evidence must not become zero.

**Workflow continuity**

Handoffs to Market, Research, Watchlist, or Stock routes remain canonical and locale-aware.

**Validation focus**

Guest and authenticated states, route title/identity, responsive smoke, overflow, data-state language, passive-load behavior.

## 13.2 Market Overview

**Purpose**

Answer: “What is the current market environment?”

**First viewport**

- bounded observation;
- primary market trend surface;
- strongest supporting drivers;
- data quality and as-of;
- next inspection path.

**Primary surface**

A chart/table/workbench combination, not equal-weight cards.

**Evidence and states**

- official, proxy, delayed, partial, and unavailable rows remain distinguishable;
- partial payload preserves useful evidence;
- diagnostics remain secondary.

**Read boundary**

Page load does not activate providers or trigger Scanner.

**Validation focus**

Partial data, dense quote overflow, responsive composition, heading hierarchy, consumer-safe error state.

## 13.3 Research Radar

**Purpose**

Prioritize real research candidates and explain why they deserve inspection.

**First viewport**

- queue identity and scope;
- candidate reason;
- evidence strength and limitations;
- freshness;
- next research action.

**Primary surface**

Research queue plus explanation/evidence composition.

**Evidence and states**

- no fake candidates;
- no recommendation semantics;
- factor visualization only when real factors exist;
- empty queue is a valid state.

**Validation focus**

Candidate identity, explanation, empty/partial states, stock handoff, no-advice copy.

## 13.4 Stock Research and Stock Structure

**Purpose**

Explain why a canonical symbol matters, what evidence exists, and where confidence is limited.

**First viewport**

- canonical symbol/market identity;
- quote/data state;
- bounded observation;
- primary price/structure surface;
- evidence reliability;
- next checks.

**Primary surface**

Price/structure research workspace with memo and evidence ledger.

**Evidence and states**

- Stock Structure identity must remain distinct from generic stock research;
- loading, completed, insufficient evidence, and unavailable remain separate;
- chart gaps and missing fundamentals/events remain honest;
- completed-page test identity must not appear in loading state.

**Workflow continuity**

Watchlist, report, comparison, and validation handoffs use existing routes and permissions.

**Validation focus**

Direct deep link, refresh, loading/completed separation, consumer withholding, no-advice, responsive chart/evidence layout.

## 13.5 Watchlist

**Purpose**

Act as a recurring research-task ledger, not a bookmark list.

**First viewport**

- list identity;
- meaningful row/queue or true empty state;
- freshness and evidence gaps;
- primary handoff to research or discovery.

**Primary surface**

Compact research ledger with contextual row actions.

**Evidence and states**

- empty route remains on the canonical Watchlist page;
- no fake saved rows;
- owner isolation and symbol identity are preserved;
- research overlay may be partial without forging readiness.

**Mutation boundary**

Passive load does not add/remove symbols or run Scanner. Explicit mutation uses existing owner and one transition.

**Validation focus**

Empty state, row identity, owner isolation, overlay failure, stock handoff, mobile action reachability.

## 13.6 Scanner

**Purpose**

Run an explicit candidate-discovery workflow and explain readiness or blockers.

**First viewport**

- scanner identity and scope;
- configuration/readiness;
- visible primary action;
- data limitations;
- result or honest idle/blocked state.

**Primary surface**

Input controls plus candidate results table/workbench.

**Evidence and states**

```text
idle
loading
blocked
empty
error
ready
```

- only real candidates render;
- candidate ranking/scoring remains backend-owned;
- missing universe/history/quote evidence fails closed.

**Mutation boundary**

Passive load does not execute or refresh Scanner. One explicit action starts one intended run.

**Validation focus**

Primary action visibility, blocked/readiness states, no duplicate execution, candidate Analyze handoff, responsive controls/results.

## 13.7 Backtest and Compare

**Purpose**

Validate a research rule with deterministic execution and inspect where it breaks.

**First viewport**

- readiness separate from result;
- run identity and assumptions;
- result only when execution/stored evidence exists;
- limitations and next validation path.

**Primary surface**

Configuration or result workbench with equity/benchmark/drawdown and ledger where real data exists.

**Evidence and states**

- no result before real execution;
- history selection must not trigger compare prematurely;
- compare API runs only in the compare workflow;
- no optimizer, winner, return promise, or allocation advice.

**Mutation boundary**

Passive result/readback pages do not execute a run.

**Validation focus**

Deterministic result, no-result gate, stored readback, compare lifecycle, copy/export, scenario order, back/forward.

## 13.8 Scenario Lab

**Purpose**

Compare bounded shocks and inspect sensitivity.

**First viewport**

- explicit scenario and baseline state;
- bounded parameters;
- primary impact surface;
- evidence limitations;
- next checks.

**Evidence and states**

- request-supplied, static, fallback, sample, proxy, or stale baselines remain observation-only;
- no allocation, position, or action recommendation;
- missing baseline blocks authoritative claims.

**Mutation boundary**

Passive load does not run or persist a scenario.

**Validation focus**

Baseline classification, parameter bounds, impact explanation, no-advice, responsive impact map/table.

## 13.9 Options Lab

**Purpose**

Provide a read-only options research console where entitlement and evidence allow.

**Evidence and states**

- chain, Greeks, IV, OI, volume, methodology, entitlement, and redisplay rights remain explicit;
- fixture/dry-run/disabled providers fail closed;
- no order workflow or strategy ranking.

**Validation focus**

Observation-only copy, entitlement/readiness, missing fields, no execution mutation, table accessibility.

## 13.10 Portfolio

**Purpose**

Inspect real accounts, cash, holdings, exposure, risk, and attribution without changing accounting authority.

**First viewport**

- honest account/portfolio identity;
- real valuation/exposure or explicit unavailable state;
- freshness and missing valuation evidence;
- next research/accounting action.

**Primary surface**

Accounting/exposure ledger and analytical summary.

**Evidence and states**

- unavailable exposure is not `0.00`;
- native currency, FX, quote and as-of lineage remain clear;
- empty/onboarding state contains no fake holdings;
- preview precedes committed mutation where the existing workflow requires it.

**Mutation boundary**

Passive load does not import, sync, add transactions, or change holdings.

**Validation focus**

Owner isolation, unavailable valuation, native currency, preview/confirm, empty mobile ordering, no broker-order implication.

## 13.11 Report Preview and Export

**Purpose**

Present a bounded research report with honest observation/generated times and safe export.

**Evidence and states**

- observation time remains distinct from generation time;
- provenance, unavailable evidence, and no-advice remain visible;
- Markdown download and print/PDF use existing report ownership;
- close/Escape restores focus to the opener.

**Validation focus**

Loading/error/completed separation, copy, download, print, drawer focus, safe Markdown rendering.

## 13.12 Settings and Admin

**Settings purpose**

Manage user-owned configuration without exposing saved secrets.

- saved webhook/token values do not enter the DOM;
- replacement draft is distinct from saved configuration;
- unchanged secret fields are omitted, not sent as empty clear operations;
- reset redirects are sanitized;
- submit guards prevent duplicate mutation.

**Admin purpose**

Expose role-gated operational diagnostics and controls.

- capability gates fail closed;
- unauthorized entries remain hidden and blocked;
- diagnostics are sanitized;
- raw secrets and provider payloads never render;
- consumer navigation remains separate.

**Validation focus**

Auth/RBAC, focus, redaction, payload omission, role gates, deep-link denial, no consumer leakage.

---

# 14. Component and migration guidance — `MIGRATION_TARGET`

## 14.1 Shared ownership

Prefer existing shared components and mappings.

Before creating a new component:

1. inspect existing ownership;
2. determine whether an existing primitive can be adapted;
3. avoid duplicate data-state mappings;
4. avoid page-local compatibility layers;
5. keep API/domain interpretation outside pure presentation components.

Possible component families are illustrative, not a required parallel design system:

```text
shell
layout
data state
research memo/queue
charts
loading/empty/error/access states
```

## 14.2 Migration rules

Replace presentation and composition, not validated domain contracts.

For each migrated route:

```text
existing route and auth contract
+ existing API/read-model authority
+ existing freshness and state semantics
→ consumer presentation mapping
→ shared components
→ page composition
→ focused route/browser validation
→ obsolete page-owned UI removal
```

Do not:

- perform a big-bang rewrite;
- copy prototype routes or data;
- delete old UI before replacement parity is proven;
- preserve obsolete composition behind compatibility CSS;
- weaken functional tests solely because markup changed;
- change protected backend semantics to simplify layout;
- add `manualChunks` or architecture workarounds to hide import-authority problems.

Delete replaced page-owned wrappers, duplicate cards, dead styling, compatibility code, and tests that protect only retired visual structure after functional parity is proven.

## 14.3 Prototype interpretation

Use the HTML reference for:

- paper color relationships;
- density and proportions;
- memo/brief treatment;
- research strips;
- table rhythm;
- search/menu interaction intent;
- motion restraint;
- state and focus language.

Do not copy:

- prototype router/history code;
- local arrays;
- static prices, scores, timestamps, chart paths, conclusions, backtest results, scenario suggestions, or mock statuses.

---

# 15. Validation and Definition of Done — `CURRENT_INVARIANT`

Use Validation Economy:

```text
focused reproduction
→ owned unit tests
→ owned browser journey
→ impacted shared validation
→ typecheck / design / diff
→ broad validation only for shared boundary or milestone changes
```

A route is complete only when applicable checks pass.

## 15.1 Product

- one clear research question;
- bounded current observation or honest inability to conclude;
- evidence, reliability, limitations, and next checks in the right hierarchy;
- no advice language;
- no fake runtime data;
- no raw consumer diagnostic leakage.

## 15.2 Architecture

- canonical/localized route preserved;
- direct deep link, refresh, back/forward work;
- auth/RBAC/session preserved;
- Product Read Model/readiness authority preserved;
- no page-local competing authority;
- no uncontrolled provider or mutation side effect;
- route remains discoverable;
- unauthorized admin surfaces remain hidden and blocked.

## 15.3 Data trust

- state labels derive from real state;
- observation/as-of is honest;
- stale/delayed/proxy remain explicit;
- missing and unavailable fail closed;
- partial evidence remains readable where allowed;
- rejected evidence does not become zero or neutral.

## 15.4 Visual and interaction

- canonical token relationships;
- high density but readable;
- desktop uses horizontal space;
- table used when comparison is primary;
- chart has real analytical meaning;
- primary action is clear;
- keyboard and visible focus;
- loading, empty, partial, error, blocked, and disabled states;
- Escape and focus restoration where applicable;
- reduced motion respected.

## 15.5 Responsive

Qualify:

```text
1440x1000
1024x900
768x900
390x844
```

Check:

- no body horizontal overflow;
- contained tables and charts;
- first-viewport analytical priority;
- accessible touch/keyboard targets;
- critical actions remain reachable;
- menus preserve route discovery.

## 15.6 Runtime and console

- no unexpected pageerror;
- no production-attributable `console.error`;
- failed requests are classified;
- passive-load read-only boundary is proven;
- one user action does not duplicate mutation;
- copy/export/status feedback is accessible.

## 15.7 Baseline red

When broad validation is already red:

- capture the exact current and task-branch result;
- classify product regression, test debt, environment, or unrelated baseline;
- prove baseline equivalence where applicable;
- do not repair unrelated failures inside a bounded task;
- do not claim readiness when a required canonical gate remains red.

---

# 16. Anti-dashboard review

Before completion verify:

- no generic KPI-card wall;
- no marketing hero;
- no feature-directory layout replacing workflows;
- no all-modules-on-one-page composition;
- no decorative chart;
- no fake metric or candidate;
- no backend/debug/mock vocabulary;
- no repeated disclaimer wall;
- no giant empty placeholders;
- no glow-heavy fintech styling;
- no icon or emoji decoration without function.

---

# 17. Final design principle

If a design choice makes the interface prettier but reduces research efficiency, evidence clarity, accessibility, or truthfulness, do not make it.

WolfyStock quality comes from:

```text
清晰的研究顺序
克制的纸面质感
可解释的数据结构
高密度但不混乱的布局
诚实的数据状态
每个结论背后都有证据
```

The practical test is:

> Within roughly ten seconds, a user should understand the current bounded observation, why it matters, how reliable the evidence is, what risk or data gap matters, and what to inspect next.
