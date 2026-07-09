# WolfyStock Design System & Frontend Contract

Version: 1.1
Status: Canonical Consumer Frontend Design Contract
Audience: Codex, frontend engineers, product engineers, reviewers
Visual reference: `docs/design/reference/wolfystock-impeccable-polish-final.html`

---

## 0. How to Use This Document

`DESIGN.md` is the canonical design and implementation contract for the WolfyStock consumer frontend.

It defines:

- product positioning and user journey;
- information architecture;
- visual language and design tokens;
- layout, density, typography, tables, charts, motion, accessibility, and responsive behavior;
- page responsibilities;
- consumer-facing data-state language;
- frontend architecture boundaries;
- migration constraints for replacing the current consumer UI.

The HTML prototype is a **visual and interaction reference**, not production code and not a source of runtime truth.

When implementing or reviewing frontend work, use this precedence:

1. repository safety and engineering rules in `AGENTS.md`;
2. production behavior and protected domain contracts in the existing application;
3. this `DESIGN.md`;
4. the visual composition, proportions, density, and interaction intent of `docs/design/reference/wolfystock-impeccable-polish-final.html`;
5. task-specific acceptance criteria.

Where the prototype conflicts with real routes, auth, RBAC, localization, API contracts, Product Read Model semantics, data freshness, no-advice rules, or production data behavior, **the real WolfyStock contract wins**.

Codex must not copy the prototype as a standalone HTML application.

The production implementation must remain inside the existing WolfyStock frontend stack and reuse the current router, authentication, authorization, API clients, data contracts, tests, and domain ownership.

---

# 1. Canonical Product Direction

WolfyStock is an **Eastern paper research terminal**:

> A high-density financial research workbench for advanced retail investors and research-oriented users, using restrained paper-like visual language, professional data structure, and explainable research workflows to help users move from market context to evidence-backed observation.

The core journey is:

```text
看市场
→ 找候选
→ 看个股
→ 加入持续观察
→ 用扫描 / 回测 / 情景分析做验证
```

WolfyStock is not:

- a brokerage trading terminal;
- a buy/sell signal service;
- an investment-advice app;
- a generic SaaS dashboard;
- an admin diagnostics wall;
- a marketing landing page;
- a black neon exchange interface;
- a collection of AI-generated cards.

It should feel like:

- an interactive research morning note;
- a dense analyst workbench;
- a calm financial research terminal;
- a product where each conclusion can be traced back to evidence;
- a product where data limitations are honest but do not dominate the experience.

---

# 2. Product Positioning

## 2.1 Target users

Primary users:

- advanced retail investors;
- research-oriented traders;
- long-horizon investors who track symbols, sectors, factors, and hypotheses;
- users who understand charts and market structure but do not want backend implementation details.

Users need to answer quickly:

- What is the current market environment?
- Which candidates deserve further research?
- Why did a candidate enter the research queue?
- How strong is the evidence?
- What is stale, delayed, partial, or unavailable?
- What risk or evidence gap matters most?
- What should I inspect next?

## 2.2 Product goal

WolfyStock does not optimize for “recommendation delivery”.

It optimizes for:

> organizing evidence, understanding context, prioritizing research, and validating hypotheses.

Core principles:

1. Understand market context before interpreting individual stocks.
2. A candidate is not a recommendation; it is a research-priority signal based on available evidence.
3. A stock page must explain why the symbol matters and where confidence is limited.
4. Watchlist is a research task ledger, not a bookmark list.
5. Scanner, Backtest, and Scenario Lab are validation tools.
6. Conclusions must return to evidence, freshness, risk, and next observation steps.
7. Honest data limitations must not turn the consumer experience into a diagnostics interface.

---

# 3. Non-Negotiable Product Rules

## 3.1 Conclusion first

Core consumer pages should follow this order:

```text
1. 当前状态 / 当前观察
2. 为什么
3. 数据是否足够可靠
4. 下一步检查什么
5. 详细证据与限制
```

Do not lead with:

- raw tables;
- backend health;
- provider state;
- contract version;
- missing-field walls;
- technical diagnostics;
- long disclaimers.

## 3.2 Evidence before confidence theater

Confidence, score, radar shape, and state labels are meaningful only when grounded in real product data.

Do not:

- invent a score for visual completeness;
- render fake candidates;
- fabricate timestamps;
- mark stale data as current;
- substitute sample fixtures into production runtime;
- display static prototype values as live product data.

## 3.3 No-advice boundary

Consumer UI must not use action language that reads as investment advice.

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

Preferred research-language patterns:

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

## 3.4 Consumer vs. Admin boundary

Consumer surfaces must not expose raw internal diagnostics.

Examples of forbidden consumer language:

```text
provider_missing
data_disabled
sourceClass
noExternalCalls
providerCallsEnabled
contractVersion
failClosed
readiness_blocked
internal enum names
cache internals
raw lineage JSON
schema versions
provider routing decisions
```

Map these to bounded consumer language such as:

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

Admin and operator surfaces may retain deeper diagnostics when authorized.

## 3.5 Show / compact / hide rule

For optional evidence modules:

```text
3+ meaningful real fields → show full module
1–2 meaningful real fields → compact summary
0 meaningful real fields → hide or collapse to a bounded empty state
```

Do not render:

- giant empty tables;
- dozens of “待补” cells;
- placeholder dashboards;
- fake numbers to preserve layout symmetry.

---

# 4. Production Frontend Architecture Contract

## 4.1 Keep the current application stack

The visual prototype uses native HTML/CSS/JavaScript. That is a reference implementation only.

The production WolfyStock frontend must continue using the existing repository application stack, including the current React/Vite architecture and existing frontend ownership boundaries.

Do not replace the production app with:

- standalone `.html` pages;
- prototype `history.pushState` routing;
- local hardcoded stock arrays;
- a parallel frontend app;
- a new framework;
- a new router;
- a new auth system.

Do not add a new charting, state-management, animation, or UI framework merely because the prototype uses a visual effect that can already be implemented with existing project capabilities.

## 4.2 Preserve validated production contracts

A frontend redesign must preserve:

- canonical routes and localized routes;
- deep-link behavior;
- browser back/forward behavior;
- refresh behavior;
- session restoration;
- logout semantics;
- auth gates;
- RBAC;
- admin-only visibility;
- safe redirect handling;
- current API ownership;
- Product Read Model authority;
- consumer presentation boundary;
- Near-Live coverage and freshness semantics;
- Watchlist symbol identity;
- Portfolio preview/confirm semantics;
- Backtest readiness vs. execution distinction;
- fail-closed behavior;
- UAT no-live-provider isolation.

Visual migration must not weaken or bypass these contracts.

## 4.3 Required render pipeline

Production consumer pages should follow:

```text
API DTO
→ domain/read-model interpretation
→ Consumer View Model
→ consumer components
→ page composition
```

Avoid:

```text
API DTO
→ page directly reads raw enums and backend flags
```

Pages must not independently reinterpret readiness.

The Product Read Model remains authoritative where already integrated.

## 4.4 Consumer View Model principle

A consumer-facing view model should provide bounded presentation data such as:

```ts
type ConsumerDataState = {
  label:
    | '实时'
    | '延迟'
    | '部分延迟'
    | '历史数据可用'
    | '历史样本不足'
    | '数据源降级'
    | '暂无数据'
    | '代理数据'
  tone: 'positive' | 'neutral' | 'warning' | 'danger' | 'muted'
  asOf?: string
  detail?: string
}
```

This is an example shape, not a requirement to create a duplicate domain model if the repository already has an equivalent consumer boundary.

Prefer extending existing presentation ownership over adding parallel mappings.

## 4.5 Prototype data is not production data

All prices, symbols, candidate counts, metrics, scores, timestamps, chart paths, and conclusions inside the HTML prototype are illustrative.

They must never be copied as:

- production defaults;
- runtime fallback values;
- sample-only states displayed as current;
- hidden fixture data in user-facing routes.

The prototype defines **composition and visual hierarchy**, not factual content.

---

# 5. Information Architecture

## 5.1 Primary consumer journey

The product journey remains:

```text
看市场
→ 找候选
→ 看个股
→ 加入持续观察
→ 用扫描 / 回测 / 情景分析做验证
→ 检视真实持仓暴露
```

The top navigation must express that journey through a coherent hierarchy, but it must **not** mechanically copy the reference prototype's literal labels or flatten every route into a first-level item.

Navigation hierarchy is determined by:

1. user task and mental model;
2. frequency and continuity of use;
3. whether the surface owns an independent workflow;
4. whether several routes form one coherent task domain;
5. route discoverability;
6. role and authorization boundary;
7. responsive constraints.

The current recommended production hierarchy is:

```text
首页

市场 ▾
  市场总览
  流动性监测
  板块轮动
  其他真实存在且属于市场环境判断的模块

研究 ▾
  研究雷达
  个股研究
  扫描器

观察列表

验证 ▾
  回测
  情景实验室
  其他真实存在且属于研究假设验证的工具

持仓
```

Admin/operator entry points should remain role-gated and visually separated, preferably through the authorized account/admin entry or the dedicated admin shell rather than ordinary consumer task groups.

This hierarchy is the canonical default for the currently known product domains. Before changing placement, audit the real production route inventory and classify each surface. A documented, evidence-based change is allowed when the product workflow materially evolves.

Do not:

- copy the prototype navigation literally without checking production ownership;
- create first-level groups with no discoverable child destinations;
- hide meaningful product routes merely to reduce navigation density;
- place routes according to backend package names or implementation ownership;
- expose admin/operator surfaces to unauthorized consumer roles;
- create menu entries for nonexistent routes.

## 5.2 Navigation classification

Classify production surfaces before changing the shell:

```text
PRIMARY_WORKSPACE
PRIMARY_TASK_DOMAIN
SECONDARY_DOMAIN_TOOL
CONTEXTUAL_RESEARCH_ENTRY
ROLE_GATED_ADMIN_SURFACE
ACCOUNT_UTILITY
LEGACY_OR_DUPLICATE_ENTRY
```

Interpretation:

- `PRIMARY_WORKSPACE`: high-frequency, persistent workspace with an independent task loop; may remain a first-level destination.
- `PRIMARY_TASK_DOMAIN`: first-level parent that groups multiple coherent child surfaces.
- `SECONDARY_DOMAIN_TOOL`: route that belongs under a primary task domain.
- `CONTEXTUAL_RESEARCH_ENTRY`: reachable from the relevant workflow and not necessarily duplicated in global navigation.
- `ROLE_GATED_ADMIN_SURFACE`: permission-gated operational surface, separated from ordinary consumer navigation.
- `ACCOUNT_UTILITY`: locale, theme, account, session, and related utilities.
- `LEGACY_OR_DUPLICATE_ENTRY`: historical or redundant entry that must be justified before remaining visible.

A grouped first-level item is valid only when its children share a clear user task. Group labels must describe user intent, not implementation structure.

Every meaningful production surface must have at least one discoverable path:

```text
global navigation
or
grouped navigation
or
clear contextual handoff
```

No canonical consumer route should become an accidental orphan after shell changes.

## 5.3 Route behavior

Every production page must:

- keep current canonical route identity;
- preserve locale prefixes;
- support direct address-bar navigation;
- survive refresh;
- support back/forward history;
- preserve auth state correctly;
- preserve query parameters where contractually meaningful;
- use safe redirects only.

Grouped navigation must additionally:

- expose child destinations on pointer and keyboard interaction according to the component contract;
- allow Escape to close an open menu;
- maintain visible focus;
- mark the active child;
- also communicate active state on the parent group;
- preserve discoverability at tablet and mobile widths;
- never require hover as the only way to reach a child route.

## 5.4 Functional placement guidance

Default placement for the currently known product surfaces:

### Market domain

```text
市场
├─ 市场总览
├─ 流动性监测
└─ 板块轮动
```

These surfaces answer the common question:

> 当前市场环境是什么？

Additional market-environment routes may join this domain only when their primary responsibility is market context, regime, liquidity, breadth, rotation, macro, or related environmental evidence.

### Research domain

```text
研究
├─ 研究雷达
├─ 个股研究
└─ 扫描器
```

Scanner belongs here by default because its primary product role is candidate discovery and research prioritization. Scanner ranking, scoring, candidate selection, and execution semantics remain protected backend/runtime contracts; navigation placement does not change them.

### Continuous research workspace

```text
观察列表
```

Watchlist remains a first-level workspace by default because it is a research-task ledger and recurring review surface, not a bookmark utility.

### Validation domain

```text
验证
├─ 回测
└─ 情景实验室
```

These tools evaluate hypotheses or sensitivity. Readiness must remain distinct from execution or durable result state.

### Portfolio workspace

```text
持仓
```

Portfolio may remain first-level because it owns an independent accounting and exposure-review workflow. Navigation changes must not alter accounting truth, ledger semantics, cost basis, P&L, FX, or owner isolation.

## 5.5 Admin and specialized surfaces

Admin surfaces:

- remain visually and navigationally separated from consumer research surfaces;
- remain permission-gated;
- may use deeper diagnostic vocabulary;
- must not appear merely because a user can guess the route;
- should use the existing role-aware account/admin entry or dedicated admin shell.

Existing specialized surfaces such as Decision Cockpit may remain available through current product routes and contextual navigation. Do not force every specialized route into the global top navigation.

---

# 6. Visual Direction

## 6.1 One-line creative direction

> WolfyStock is a breathing Eastern financial research paper: soft, restrained, dense, and analytical, using artful but readable data visualization to clarify market structure.

## 6.2 Mood

Visual keywords:

- Eastern philosophy;
- paper research;
- restrained technology;
- professional finance;
- high information density;
- calm evidence;
- analytical memo;
- subtle craftsmanship.

Avoid:

- blue-purple fintech gradients;
- black neon exchange styling;
- heavy glow effects;
- excessive glassmorphism;
- card walls;
- AI illustration;
- emoji icon rows;
- icon-per-card decoration;
- marketing hero layouts;
- generic admin-dashboard styling;
- decorative metrics without research purpose.

---

# 7. Design Tokens

The following values are the canonical starting point for the new consumer theme.

Implementation may adapt token names to the repository's existing token system, but the visual relationships should remain consistent.

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

## 7.1 Color roles

- `paper`: application background;
- `surface`: main research panel;
- `sage`: brand action, selected state, primary structural accent;
- `sage-deep`: active navigation and important text;
- `gold`: rare emphasis;
- `blue`: secondary/third analytical dimension;
- `danger`: risk and negative state;
- `ok`: positive/available state;
- `warn`: caution and ambiguous state;
- `muted`: explanatory text;
- `line`: paper-like separation.

## 7.2 Gold rule

Gold `#D4A574` is the unique accent color.

Use sparingly for:

- Fig / Plate annotations;
- key badges;
- secondary chart curve;
- important caution or research highlight;
- limited secondary emphasis.

Do not use gold as a large-area background.

## 7.3 Semantic color separation

Do not reuse one color for unrelated semantics.

Keep distinct visual meanings for:

- brand/selection;
- price up;
- price down;
- data available;
- stale/delayed;
- warning;
- unavailable.

A selected tab and a positive market move should not look semantically identical.

---

# 8. Typography

## 8.1 Font roles

```css
:root {
  --font-display:
    "Noto Serif SC",
    "Songti SC",
    "STSong",
    "Iowan Old Style",
    Georgia,
    serif;

  --font-body:
    "Inter",
    -apple-system,
    BlinkMacSystemFont,
    "Segoe UI",
    system-ui,
    sans-serif;

  --font-mono:
    "SFMono-Regular",
    "JetBrains Mono",
    ui-monospace,
    Menlo,
    monospace;
}
```

Do not bundle font files into the repository merely to reproduce the prototype unless separately approved.

Use system/fallback fonts gracefully.

## 8.2 Display type

Use for:

- page titles;
- research conclusions;
- Analyst Memo headlines;
- major section headings.

Tone:

- stable;
- editorial;
- research-report-like;
- not advertising-heavy.

## 8.3 Body type

Use for:

- navigation;
- forms;
- buttons;
- tables;
- descriptions;
- body copy.

## 8.4 Mono type and numeric alignment

Use for:

- stock symbols;
- prices;
- percentages;
- dates;
- time;
- metrics;
- Fig/Plate annotations.

Financial numbers should use:

```css
font-variant-numeric: tabular-nums lining-nums;
```

Avoid exaggerated negative tracking that harms multi-digit number readability.

---

# 9. Layout System

## 9.1 Desktop workbench

Canonical wide layout:

```css
.shell {
  width: 100%;
  max-width: 1880px;
  margin: 0 auto;
  padding: 14px 18px 38px;
}
```

WolfyStock is a professional analysis platform. Desktop layouts should use available horizontal space.

Do not default to a narrow SaaS content column.

## 9.2 Grid

Use a 12-column grid:

```css
.grid-12 {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 10px;
}
```

Common spans:

```text
span-3  parameter panel / narrow sidebar
span-4  side summary / metric group
span-5  research queue / medium sidebar
span-7  main work area
span-8  large chart
span-9  results table
span-12 full-width ledger / table
```

## 9.3 Density

Preferred desktop patterns:

- chart + analytical summary side by side;
- configuration sidebar + results table;
- main trend panel + metric panel;
- queue + explanation panel;
- chart + table visible in one working view;
- compact ledgers and rows.

Avoid:

- oversized hero blocks;
- excessive vertical whitespace;
- generic card grids with no analytical hierarchy;
- one-column desktop pages;
- large empty panels;
- repeated decorative containers.

## 9.4 Spacing

Guidance:

- page outer spacing: restrained;
- panel padding: roughly 13–16px;
- major grid gap: 8–10px;
- local row gap: 6–8px;
- use dividers before adding more nested cards.

---

# 10. Surface Hierarchy

Use four levels of visual hierarchy:

```text
paper background
→ main panel
→ bounded secondary card / row / table
→ content and numeric data
```

## 10.1 Panel

Primary work-area container.

Reference:

```css
.panel {
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: rgba(251, 248, 243, .76);
  box-shadow: var(--shadow);
  overflow: hidden;
}
```

Use for:

- main charts;
- Analyst Memo;
- research queue;
- scanner results;
- backtest results;
- scenario impact map;
- large tables.

## 10.2 Card

Secondary information block.

Reference:

```css
.card {
  padding: 13px;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, .5);
}
```

Cards must carry specific research content.

Do not create a card merely to wrap:

- one label;
- one empty status;
- one decorative icon;
- navigation shortcuts that belong in the top nav.

## 10.3 Brief / Analyst Memo

The highest-priority conclusion block:

```text
当前观察
→ 简要解释
→ 下一步检查
```

Reference:

```css
.brief {
  display: grid;
  gap: 9px;
  padding: 14px;
  border-radius: 14px;
  border: 1px solid rgba(107, 143, 113, .2);
  background: linear-gradient(
    180deg,
    rgba(220, 231, 220, .55),
    rgba(255, 255, 255, .36)
  );
}
```

This block must not fabricate a strong conclusion when PRM/readiness forbids one.

## 10.4 Research Strip

Use for compact research queues.

Structure:

```text
symbol + reason
score / evidence strength
data state
contextual action
```

Useful on:

- Home research order;
- Research Radar queue;
- Watchlist task summary.

Do not use it as a replacement for tables where comparison is the primary task.

---

# 11. Navigation and Global Shell

## 11.1 Top navigation

Requirements:

- sticky;
- paper-like translucent background;
- current route highlighted;
- locale-aware links;
- keyboard accessible;
- primary research journey legible through first-level workspaces and task domains;
- grouped domains expose complete and discoverable child destinations;
- standalone first-level workspaces are reserved for high-frequency or independent task loops;
- role-aware Admin entry remains separated from ordinary consumer task groups;
- account menu retained;
- language switch retained where currently supported;
- theme setting retained where currently supported;
- no route contract regression;
- no accidental route orphaning.

The shell may use grouped navigation such as `市场`, `研究`, and `验证` when route inventory and user workflow support those domains.

Do not require all consumer pages to be first-level links. Do not hide child routes behind a parent label that has no usable menu, drawer, popover, or equivalent discoverable interaction.

## 11.2 Global search

Search is a core product interaction.

Expected flow:

```text
input
→ debounced existing symbol-resolution owner
→ exact/fuzzy results
→ canonical symbol identity
→ market context
→ existing canonical stock route
```

Do not implement production search with the prototype's local `stocks[]` array.

Requirements:

- `⌘K` / `Ctrl+K`;
- visible label or accessible name;
- keyboard navigation;
- escape closes result panel;
- explicit no-results state;
- loading state;
- correct canonical symbol and market handoff;
- no provider live probe merely because the search box opened.

## 11.3 Grouped menus and overflow menus

Requirements:

- open and close predictably;
- Escape closes;
- outside click closes where the interaction model uses a popover;
- `aria-expanded` on the controlling element;
- keyboard navigation between parent and child items;
- role-aware items;
- active child state;
- active parent-group state when a child route is open;
- no hover-only access path;
- mobile and tablet equivalent that preserves all meaningful destinations;
- deterministic ordering based on research workflow, not alphabetical backend naming.

Use an overflow or `更多` menu only for genuinely secondary or low-frequency surfaces. Do not use it as a dumping ground for major workflows merely to keep the header visually sparse.

---

# 12. Data State Presentation

## 12.1 Consumer vocabulary

Preferred bounded state labels:

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

## 12.2 Data state source of truth

Consumer badges must be derived from real readiness/freshness/provenance ownership.

Never hardcode:

```tsx
<Badge>实时</Badge>
```

without real state support.

The intended flow is:

```text
backend PRM / Near-Live coverage / domain readiness
→ consumer presentation mapping
→ DataStateBadge / FreshnessStamp
```

## 12.3 Freshness

Where materially relevant, show:

- state;
- as-of time/date;
- delayed/stale context;
- per-family freshness when aggregate timestamps would mislead.

Do not use a single newest timestamp to make older critical evidence appear current.

Do not use a single oldest timestamp to imply every evidence family is equally old.

Prefer bounded per-family freshness or an explicit aggregate window where needed.

---

# 13. Tables and Ledgers

Tables are a core part of the WolfyStock professional identity.

Use tables for:

- Watchlist ledger;
- Scanner results;
- Radar queue ledger where comparison matters;
- Backtest trades;
- evidence ledger;
- peer/comparable analysis.

Requirements:

- clear headers;
- `<caption>` or accessible equivalent;
- compact row height;
- tabular numeric alignment;
- light hover state;
- sticky header where long tables benefit;
- horizontal scrolling on small screens;
- keyboard-accessible row actions;
- no card-per-row conversion on desktop.

For dense tables, prioritize:

```text
identity
state
change
reason
freshness
next research step
action
```

over dozens of low-value columns.

---

# 14. Buttons and Actions

Buttons should use concrete research verbs.

Preferred labels:

```text
看证据
看证据账本
加入观察
加入雷达
运行扫描
重试扫描
运行回测
重算冲击路径
市场总览
研究雷达
```

Avoid generic or marketing labels:

```text
了解更多
立即开始
智能分析
一键洞察
AI 洞察
```

Every interactive control must support:

- default;
- hover;
- active/pressed where relevant;
- `focus-visible`;
- disabled;
- loading where asynchronous.

A button that triggers a write must not look identical to a passive drill-down action.

---

# 15. Charts and Visualization

## 15.1 General rules

Charts are primary financial research surfaces, not decoration.

Requirements:

- real data only;
- no static prototype curve in production;
- clear axis/time context where needed;
- tooltips or hover inspection for detailed financial series;
- empty/stale/loading/error states;
- range controls;
- bounded data status;
- accessible label/description.

Avoid:

- 3D charts;
- neon gradients;
- decorative geometry with no analytical meaning;
- chart animation that obscures data comparison.

Reuse existing chart ownership and dependencies where possible.

Do not add a new chart library solely to reproduce a prototype drawing effect.

## 15.2 Stock chart

Stock research chart should support the real data available to the product:

- OHLC/candlestick where supported;
- volume;
- relevant moving averages;
- range selection;
- hover/crosshair inspection;
- freshness/as-of context;
- honest unavailable or partial state.

## 15.3 Market chart

Market Overview should prioritize:

- primary index/proxy trend;
- clearly labeled proxy use;
- range control;
- key risk/macro metrics;
- market-driver context.

## 15.4 Backtest chart

Backtest should separate:

- equity curve;
- benchmark comparison;
- drawdown;
- metrics;
- sample/trade ledger.

Readiness is not a result.

Do not display example performance when a real backtest has not run.

---

# 16. Signature Visualization

The WolfyStock signature visual device is:

> a hand-drawn-feeling dashed concentric-grid multi-dimensional research radar using sage, gold, and soft blue.

Use selectively on:

- Research Radar;
- Scenario Lab;
- occasional high-value Home summary.

Color roles:

- sage: main structure / trend / quality;
- gold: valuation / odds / secondary signal;
- blue: risk / volatility / third analytical dimension.

The reference prototype uses an SVG roughness filter such as:

```svg
<filter id="rough">
  <feTurbulence
    type="fractalNoise"
    baseFrequency=".018"
    numOctaves="2"
    seed="8"
  />
  <feDisplacementMap in="SourceGraphic" scale="1.25" />
</filter>
```

Rules:

- this is a brand memory device, not a universal chart;
- underlying dimensions must be real and explained;
- factor bars should remain available where precise comparison is more useful than radar shape;
- do not render a radar with invented factors or scores.

---

# 17. Motion

Motion is restrained and functional.

Allowed:

- short page/section entry;
- small menu transition;
- search-result transition;
- candidate selection feedback;
- scanner state transition;
- subtle chart line reveal where it does not impair reading.

Rules:

- prefer `transform` and `opacity`;
- keep motion short;
- no bouncing;
- no particles;
- no scrolling spectacle;
- no motion that delays data access;
- cancel or clean up long-running animation when route changes;
- support reduced motion.

Required reduced-motion behavior:

```css
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: .001ms !important;
    animation-iteration-count: 1 !important;
    scroll-behavior: auto !important;
    transition: none !important;
  }
}
```

---

# 18. Accessibility

New consumer UI must include:

- skip link;
- semantic landmarks;
- accessible navigation label;
- `aria-current="page"` for current route;
- labeled search;
- `aria-live` only for meaningful async updates;
- table captions or equivalent accessible naming;
- keyboard operation;
- Escape behavior for overlays/menus;
- `focus-visible`;
- no state communicated by color alone;
- SVG charts with `role="img"` and useful label/description;
- reduced-motion support;
- sufficient contrast for text and state labels.

Keyboard requirements for search:

```text
⌘K / Ctrl+K → focus search
Arrow keys   → move through results where implemented
Enter        → open selected result
Escape       → close results / release focus state
```

---

# 19. Responsive Behavior

## 19.1 Wide desktop: 1440–1920+

Primary target.

Requirements:

- full-width research workbench;
- multi-column density;
- charts and tables may coexist;
- side-by-side conclusion + chart;
- 12-column layout;
- no narrow center column.

## 19.2 Tablet

Requirements:

- chart and sidebar stack when needed;
- six-column metrics may become three columns;
- navigation may scroll horizontally;
- table remains table, with horizontal scroll;
- important action remains visible.

## 19.3 Mobile

Do not simply stack the desktop page into 30 screens.

Mobile priority:

```text
compact top bar
→ search
→ headline / current observation
→ one primary chart or primary task
→ horizontally scrollable key metrics where useful
→ compact next checks
→ accordion evidence
→ table horizontal scroll
```

Requirements:

- single-column primary flow;
- preserve all critical actions;
- avoid squashing charts;
- avoid converting dense comparative tables into dozens of large cards;
- prioritize research sequence over visual parity with desktop.

---

# 20. Content Voice

WolfyStock should sound like a calm professional research assistant.

Tone:

- clear;
- restrained;
- specific;
- evidence-aware;
- conclusion first;
- risk-aware;
- never sensational.

Good patterns:

```text
市场允许继续研究强势股，但不支持无条件追高。
趋势仍在，但追价条件不足。
候选不是推荐，是当前证据密度较高的研究对象。
下一步：观察开盘后是否守住近 20 日均线区域。
当前数据支持继续观察，不支持直接行动。
风险偏好回升，但趋势确认仍需要成交量配合。
```

Avoid:

```text
马上买入
暴涨机会
十倍潜力
稳赚
错过就没了
AI 神器
智能洞察
一站式平台
```

Avoid raw English backend copy in Chinese consumer pages.

---

# 21. Required Page Contracts

The sections below define product responsibility and composition intent. They do not require exact pixel matching to the prototype.

## 21.1 Home

Purpose:

> 今天先看什么？

Home is a daily research entry point, not a feature directory.

Primary composition:

```text
Morning Decision Note
Research Queue
Watch Changes
Index Path
Data Ledger
```

Must provide:

- one market observation sentence;
- key market indicators;
- research order / queue;
- meaningful watchlist changes;
- data state;
- contextual entry points to Market, Radar, and Stock research.

Do not show:

- giant empty state because no symbol is selected;
- feature-directory cards;
- diagnostic walls;
- fake candidates;
- repeated disclaimers.

When no real research candidates exist:

- show an honest empty queue;
- explain the current blocking reason in consumer language;
- provide the next meaningful research action;
- do not populate the prototype's AAPL/NVDA/MSFT examples.

## 21.2 Market Overview

Purpose:

> 当前市场水温如何？哪些力量在推动？

Primary composition:

```text
market observation / regime brief
main index or proxy path
key metrics
market drivers
bounded data state
```

Key dimensions may include, where real data exists:

- SPY / QQQ or actual supported market proxies;
- VIX;
- DXY;
- US10Y;
- breadth;
- sector rotation;
- risk appetite.

Do not:

- turn the page into a provider diagnostics wall;
- render 17 unavailable data cards;
- fabricate a regime when critical evidence blocks a strong conclusion.

## 21.3 Research Radar

Purpose:

> 哪些标的值得进入研究，为什么？

Primary composition:

```text
candidate queue
selected candidate detail
factor contribution
risk / limitation
next research check
queue ledger
signature radar or precise factor bars
```

Each real candidate should expose bounded consumer information such as:

- symbol and name;
- market identity;
- candidate reason;
- data state;
- evidence strength;
- key limitation;
- next research check;
- drill-down to canonical stock route;
- add-to-watchlist where supported.

If there are zero candidates:

- show zero candidates;
- do not fabricate a visual queue;
- explain whether the blocker is universe membership, market data, candidate generation, or another bounded consumer state;
- provide a safe next step.

## 21.4 Stock Research

Purpose:

> 这只股票现在为什么值得看，风险在哪里？

This is a core product surface.

Primary composition:

```text
identity + price state
main price path
Analyst Memo
key metrics
evidence summary
risk trigger / invalidation evidence
next research check
Evidence Ledger
```

Must preserve:

- canonical symbol and market identity;
- quote freshness;
- OHLCV data state;
- PRM authority;
- strong-conclusion withholding when required;
- confidence limitations;
- evidence gaps;
- bounded provenance.

Suggested first-screen layout:

```text
7 columns: main chart
5 columns: Analyst Memo + key metrics
```

Detailed evidence belongs below or behind deliberate disclosure.

Do not show:

- raw backend field names;
- large missing-field walls;
- fake live quote;
- investment action language;
- internal observed classification when consumer display must be withheld.

## 21.5 Watchlist

Purpose:

> 我关注的标的今天有什么变化？

Watchlist is a research-task ledger.

Primary composition:

```text
needs-review summary
important changes
full watchlist ledger
research handoff
```

Ledger columns should prioritize:

- symbol / identity;
- latest available price;
- change;
- research/structure state;
- evidence quality;
- latest trigger;
- next check;
- action.

Preserve:

- owner isolation;
- canonical symbol/market identity;
- honest freshness;
- no passive refresh side effects;
- real research handoff context.

Empty watchlist:

- remain on the canonical Watchlist route;
- preserve locale;
- show a useful empty-state path;
- do not redirect to Home merely because the list is empty.

## 21.6 Scanner

Purpose:

> 按我的条件，现在有哪些标的浮出来？

Primary composition:

```text
3-column setup panel
9-column results work area
```

Controls may include, where supported:

- market;
- strategy template;
- data completeness rule;
- Top N;
- run action.

Results should include:

- symbol identity;
- rank/score where genuinely produced;
- inclusion reason;
- risk limitation;
- data state;
- next step;
- add to Radar/Watchlist where supported.

Required UI states:

```text
idle
loading
empty
blocked
error
ready
```

Do not:

- auto-run on page read;
- use fake results;
- hide universe/data blockers behind a generic “server error”;
- expose raw lifecycle diagnostics to consumer UI.

Membership readiness, market-data readiness, and candidate-generation readiness must remain distinct.

## 21.7 Backtest

Purpose:

> 这个研究假设过去是否站得住？

Primary composition:

```text
configuration
readiness
real result workspace after execution
equity curve
drawdown
key metrics
benchmark comparison
trade ledger
Where It Breaks
```

Readiness and result are separate states.

Before execution:

- show readiness honestly;
- do not show prototype example performance as a real result.

After a real run:

- show actual metrics and actual charts;
- show assumptions and limitations;
- show sample/coverage context;
- show failure environments where available.

Never imply future return.

## 21.8 Scenario Lab

Purpose:

> 如果某个冲击发生，我关注的资产可能怎样变化？

Primary composition:

```text
scenario configuration
impact map
asset sensitivity
Watchlist mapping
explanation path
data limitations
```

Supported scenario controls may include:

- preset scenario;
- shock magnitude;
- time horizon;
- selected symbol or Watchlist scope.

Actions should use research language such as:

```text
重算冲击路径
重新评估敏感度
```

Do not display:

```text
现金权重 +5%
建议上调仓位
需降仓
```

unless the product's legal/product scope explicitly changes.

Use:

```text
流动性缓冲敏感度较高
高波动暴露需重点复核
成长资产对该情景更敏感
```

## 21.9 Portfolio

The visual prototype does not fully cover Portfolio, but WolfyStock production includes it.

Purpose:

> 我的组合暴露在哪些市场、主题和数据风险上？

Primary composition should follow the same visual system:

```text
portfolio identity / accounts
exposure summary
risk concentration
valuation freshness
import onboarding
holdings ledger
```

Preserve:

- no fake account;
- no fake holdings;
- no fake P&L;
- preview before commit;
- explicit confirmation;
- duplicate/idempotency semantics;
- broker readiness honesty;
- unavailable valuation state.

Portfolio must visually belong to the same research product without changing accounting semantics.

## 21.10 Admin

Admin surfaces are outside the core consumer visual flow.

They may reuse tokens and shell primitives, but:

- diagnostics may remain denser;
- raw provider/runtime language may remain where necessary;
- RBAC must remain strict;
- consumer navigation must not expose unauthorized admin entries;
- admin redesign must not be conflated with consumer page migration.

---

# 22. Loading, Empty, Partial, Error, and Blocked States

Every async product surface must deliberately support the states relevant to its domain.

## 22.1 Loading

Use:

- skeletons for structured content;
- spinner only for short bounded actions;
- button-level progress for explicit actions.

Do not block the entire application shell for a local panel load.

## 22.2 Empty

An empty state must answer:

```text
what is empty?
why is it empty, if known?
what can the user do next?
```

Example:

```text
当前没有研究候选。
标的池已准备，但当前条件下没有候选通过研究门槛。
可以调整筛选条件，或查看观察列表中的已有研究对象。
```

Do not show fake candidate cards.

## 22.3 Partial / stale

Readable stale data may remain visible when allowed, but must show:

- state;
- as-of;
- scope of staleness;
- bounded implication.

Do not visually treat stale as current.

## 22.4 Error

Consumer error copy should be actionable and bounded.

Avoid:

```text
API failed
backend error
null response
500 Internal Server Error
```

Prefer:

```text
当前数据暂时无法读取。
可以稍后重试，已有历史数据不会被替换。
```

when that statement is factually supported.

## 22.5 Blocked

Blocked product capabilities should explain the user-level blocker without leaking internals.

Example:

```text
当前标的池尚未准备完成，因此暂时无法运行扫描。
```

Admin drill-through may expose detailed lifecycle reasons.

---

# 23. Component Architecture Guidance

Prefer a shared design system inside the existing frontend source tree.

A possible organization is:

```text
components/
  wolfy/
    shell/
      ConsumerShell
      TopNavigation
      GlobalStockSearch
      MoreMenu
      AccountMenu

    layout/
      Workspace
      PageHeader
      ResearchGrid
      SplitWorkbench
      SectionRule

    data/
      DataStateBadge
      FreshnessStamp
      MetricTile
      EvidenceSummary
      DataTrustDisclosure

    research/
      AnalystMemo
      ResearchStrip
      CandidateCard
      FactorBars
      SignatureRadar
      ResearchQueue

    charts/
      PriceChart
      MarketTrendChart
      MiniSparkline
      DrawdownChart

    states/
      LoadingState
      EmptyState
      PartialDataState
      ErrorState
      AccessGate
```

This is guidance, not a requirement to duplicate existing components.

Before creating a component:

1. inspect existing ownership;
2. reuse or adapt existing stable components;
3. avoid parallel design systems;
4. avoid duplicate consumer-state mappings.

---

# 24. Migration Rules for Replacing the Current Consumer UI

The migration should replace **presentation and composition**, not validated domain contracts.

Before changing global navigation:

```text
inventory real consumer routes
→ trace current entry points
→ classify functional ownership
→ classify first-level vs grouped vs contextual placement
→ verify role visibility
→ implement shell hierarchy
→ validate direct/deep links, active state, keyboard, responsive discovery
```

Do not begin a navigation migration by copying prototype labels or by reorganizing routes from memory.

Recommended order:

```text
1. Design tokens + Consumer Shell
2. Shared consumer state and layout primitives
3. Market Overview
4. Stock Research
5. Home
6. Research Radar
7. Watchlist
8. Scanner
9. Backtest
10. Scenario Lab
11. Portfolio
12. Legacy consumer UI cleanup
13. Focused consumer UAT
```

Do not perform a big-bang rewrite of every route in one task.

For each migrated route:

```text
existing route contract
+ existing API ownership
+ existing auth/session behavior
+ existing PRM/freshness semantics
→ new Consumer View Model where needed
→ new design-system components
→ new page composition
```

Do not:

- create a second router;
- duplicate page state logic;
- delete old components before the new route is qualified;
- change protected backend domains merely to make the new layout easier;
- weaken tests because the UI structure changed;
- use the HTML prototype's data as fallback.

---

# 25. Reference Prototype Interpretation Rules

Use `docs/design/reference/wolfystock-impeccable-polish-final.html` as a reference for:

- color relationships;
- paper texture;
- workbench density;
- panel proportions;
- page rhythm;
- Analyst Memo treatment;
- research strips;
- table density;
- top navigation;
- search interaction intent;
- radar visual identity;
- motion restraint;
- focus states;
- loading/empty/error visual language;
- accessibility cues.

Do **not** copy from the prototype:

- `.html` route names;
- `pathToPage`;
- `history.pushState` router;
- local `stocks` arrays;
- static prices;
- static candidate scores;
- static market conclusions;
- static timestamps;
- static SVG financial time-series paths;
- example backtest results;
- example scenario allocation suggestions;
- mock statuses.

The prototype is the visual north star, not runtime truth.

---

# 26. Anti-AI and Anti-Dashboard Checklist

Before a page is considered visually complete, check:

- [ ] no blue-purple fintech gradient;
- [ ] no cheap glow halo;
- [ ] no emoji icon row;
- [ ] no icon on every card;
- [ ] no “Feature One / Feature Two” filler;
- [ ] no generic KPI-card wall;
- [ ] no marketing hero;
- [ ] no admin-dashboard feel on consumer routes;
- [ ] no feature-directory cards replacing navigation;
- [ ] no all-modules-in-one-page composition;
- [ ] no fake metric;
- [ ] no fake candidate;
- [ ] no exaggerated return promise;
- [ ] no backend/debug/mock vocabulary;
- [ ] no duplicated disclaimer wall;
- [ ] no oversized empty placeholders;
- [ ] no decorative chart without real analytical meaning.

If any answer is yes, fix it before completion.

---

# 27. Definition of Done — Shared

A migrated consumer route is not complete until all applicable checks pass.

## Product

- [ ] page answers one clear research question;
- [ ] first screen provides the bounded current observation or honest inability to conclude;
- [ ] evidence and limitations are visible in the right hierarchy;
- [ ] next research step is clear;
- [ ] no advice language;
- [ ] no fake runtime data.

## Architecture

- [ ] existing route preserved;
- [ ] localized route preserved;
- [ ] direct deep link works;
- [ ] refresh works;
- [ ] back/forward works;
- [ ] auth state preserved;
- [ ] RBAC preserved;
- [ ] PRM/readiness authority preserved;
- [ ] no new page-local readiness interpretation;
- [ ] no uncontrolled provider call introduced;
- [ ] every meaningful consumer route has a discoverable global, grouped, or contextual entry;
- [ ] grouped first-level parents expose their real child routes;
- [ ] active child and active parent-group state remain correct;
- [ ] unauthorized admin/operator entries remain hidden and blocked.

## Data trust

- [ ] status badges derive from real state;
- [ ] freshness/as-of is honest;
- [ ] stale does not look current;
- [ ] missing data fails closed;
- [ ] partial data remains readable where allowed;
- [ ] no raw internal diagnostic leaks.

## Visual

- [ ] uses canonical tokens;
- [ ] high density but readable;
- [ ] no card sprawl;
- [ ] desktop uses horizontal space;
- [ ] table used where comparison is primary;
- [ ] chart has real data and meaningful context;
- [ ] Analyst Memo / brief hierarchy is clear;
- [ ] gold accent remains sparse.

## Interaction

- [ ] keyboard usable;
- [ ] focus visible;
- [ ] loading state;
- [ ] empty state;
- [ ] error state;
- [ ] disabled state;
- [ ] Escape behavior where applicable;
- [ ] grouped navigation is not hover-only;
- [ ] grouped menus preserve child-route discoverability on desktop, tablet, and mobile;
- [ ] reduced motion respected.

## Responsive

- [ ] wide desktop qualified;
- [ ] tablet composition qualified;
- [ ] mobile research sequence qualified;
- [ ] tables remain usable;
- [ ] charts remain readable;
- [ ] critical actions remain accessible.

---

# 28. Definition of Done — Page-Specific Minimums

## Home

- [ ] market observation;
- [ ] research queue or honest empty state;
- [ ] watchlist changes or honest empty state;
- [ ] index path where data exists;
- [ ] data ledger;
- [ ] no feature-directory layout.

## Market Overview

- [ ] market observation;
- [ ] primary trend chart;
- [ ] key metrics;
- [ ] drivers;
- [ ] data state;
- [ ] no false strong conclusion.

## Research Radar

- [ ] real queue or zero-state;
- [ ] candidate reason;
- [ ] evidence strength;
- [ ] limitation;
- [ ] next check;
- [ ] factor visualization where real factors exist.

## Stock Research

- [ ] canonical symbol identity;
- [ ] quote state;
- [ ] main chart;
- [ ] Analyst Memo;
- [ ] confidence/evidence limitations;
- [ ] evidence ledger;
- [ ] consumer withholding respected.

## Watchlist

- [ ] canonical route remains on empty state;
- [ ] research-task ledger;
- [ ] freshness honesty;
- [ ] handoff to stock research;
- [ ] owner isolation preserved.

## Scanner

- [ ] input controls;
- [ ] readiness/blocked state;
- [ ] idle/loading/empty/error/ready;
- [ ] real candidate results only;
- [ ] no page-read refresh side effect.

## Backtest

- [ ] readiness shown separately from result;
- [ ] no result until real execution exists;
- [ ] equity/benchmark/drawdown where real result exists;
- [ ] assumptions and failure conditions;
- [ ] no return promise.

## Scenario Lab

- [ ] explicit scenario;
- [ ] bounded parameters;
- [ ] impact explanation;
- [ ] data limitations;
- [ ] no allocation advice language.

## Portfolio

- [ ] honest empty/onboarding state;
- [ ] preview before commit;
- [ ] no fake valuation/P&L;
- [ ] freshness and missing valuation evidence visible;
- [ ] accounting semantics unchanged.

---

# 29. Final Design Principle

If a design choice makes the interface prettier but reduces research efficiency, do not make it.

WolfyStock's aesthetic quality comes from:

```text
清晰的研究顺序
克制的纸面质感
可解释的数据结构
高密度但不混乱的布局
诚实的数据状态
每个结论背后都有证据
```

The final product test is:

> 用户打开页面后，应在约 10 秒内知道：当前市场怎样、先研究什么、为什么、风险和数据限制在哪里、下一步该检查什么。

That is the standard for every consumer-facing WolfyStock page.
