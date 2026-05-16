# WolfyStock Frontend Design Constitution

WolfyStock is a Linear-inspired professional stock research operating system.

This document is mandatory for every frontend change. Before editing any frontend file, read and follow this design system. Do not invent visual styles outside this system unless the task explicitly states why.

WolfyStock should feel like a calm, precise, low-noise research workspace for serious investors, quants, and power users.

It is not a generic SaaS dashboard, not a Web3 dApp, not a glass-card demo, and not a dense admin backend.

For page hierarchy, information-density budgets, and guided disclosure rules, also follow:

- `docs/audits/frontend-information-density-and-guidance-standard.md`
- `docs/codex/WOLFYSTOCK_TERMINAL_PRIMITIVES_USAGE.md`

---

## 0. Product Identity

WolfyStock is a professional stock research and decision-support workspace.

The UI must feel like:

- Linear-inspired product software
- calm, minimal, precise, and restrained
- institutional but approachable
- stock-research-first, not crypto-first
- task-first, not dashboard-decoration-first
- data-honest, low-noise, and decision-oriented
- keyboard/command friendly
- modern, geeky, and mature

The UI must not feel like:

- Web3 wallet/dApp interface
- dark Bootstrap admin panel
- generic SaaS analytics template
- card-heavy bento dashboard
- noisy quant terminal cosplay
- developer debug console
- colorful retail finance app
- dense Web1 table backend

Core visual direction:

```text
dark graphite canvas
thin dividers
soft surfaces
low chrome
quiet typography
restrained blue focus
green/red only for financial meaning
progressive disclosure
tables/lists/boards before cards
```

---

## 1. Core Design Principles

### 1.1 Task First

Every page must have one clear primary task.

| Page | Primary Task |
|---|---|
| Home | understand one stock’s current decision state |
| Scanner | compare ranked candidates |
| Watchlist | monitor saved symbols and evidence |
| Market Overview | understand current market regime |
| Liquidity Monitor | assess liquidity pressure |
| Rotation Radar | compare sector/theme rotation |
| Portfolio | understand exposure, P&L, and risk |
| Backtest | evaluate strategy performance |
| Options Lab | test one options hypothesis |
| Admin/Ops | operate and diagnose system state |

If a section does not support the primary task, move it below the fold, into a drawer, or behind a disclosure.

### 1.2 Low Noise Before High Density

WolfyStock can be dense, but only after hierarchy is clear.

Do not increase density by exposing every field.

Good density:

```text
important data appears early
secondary data is available but quiet
debug data is collapsed
rows are scannable
actions are close to context
```

Bad density:

```text
chip clouds
repeated N/A fields
raw provider labels
large empty panels
all actions visible at once
diagnostics before the main task
```

### 1.3 Board/List/Table First

Use the surface that matches the task.

| Task Type | Preferred Surface |
|---|---|
| compare candidates | ranking board / table |
| monitor assets | list / table |
| inspect one stock | research console |
| evaluate backtest | chart + report tabs |
| operate admin state | ops table + drawer |
| long-form generated analysis | report surface |

Cards are allowed, but they are not the default.

### 1.4 Progressive Disclosure

Default UI should show only what is needed for the decision.

Collapse by default:

- raw diagnostics
- provider traces
- internal counters
- generated/failed candidate details
- schema/state payloads
- execution assumptions
- long data-quality explanations
- history comparisons
- debug-only notes

Expose these through:

- disclosure rows
- drawers
- tabs
- command palette
- details panels

### 1.5 Linear-Inspired Restraint

Use quiet, precise UI.

Prefer:

```text
thin dividers
subtle panels
short labels
clean alignment
consistent spacing
low-saturation accents
calm hover/focus states
```

Avoid:

```text
large glow
heavy glass blur
neon gradients
bulky rounded cards
busy chip clusters
decorative panels
over-explained helper text
```

---

## 2. Hard Anti-Patterns

These are forbidden in normal frontend UI.

### 2.1 Card-First Dashboards

Do not turn every piece of information into a card.

Avoid:

```text
card inside card
metric card grids for minor fields
large empty-state cards
diagnostics as cards
history as cards before the main task
```

Use instead:

```text
rows
tables
thin strips
section dividers
inline empty rows
drawers
compact disclosures
```

### 2.2 Bento as Default Architecture

Bento grids are not the default layout strategy.

Bento may be used only when:

- the page is intentionally editorial/report-like;
- there are a few high-value summary blocks;
- each block has clear hierarchy and purpose.

Do not use bento to organize complex workflows such as Scanner, Backtest, Admin logs, or Watchlist.

### 2.3 Ghost Glass Everywhere

Do not apply glass panels, blur, and rounded containers by default.

Avoid overusing:

```tsx
backdrop-blur-md
rounded-[16px]
rounded-2xl
shadow-glow
bg-white/[0.02] on every section
border border-white/10 on every block
```

A page with 20 translucent bordered surfaces is not minimal.

Use surfaces sparingly. Content should carry the hierarchy.

### 2.4 Web3 / dApp Aesthetic

Do not use wallet/dApp visual language unless the feature explicitly requires it.

Avoid:

```text
wallet chips
chain badges
purple neon everywhere
crypto-style glowing pills
dApp navigation patterns
```

WolfyStock is a stock research platform first.

### 2.5 Debug/Provider/Internal Leakage

Default user UI must not expose raw debug strings.

Do not show these in primary UI:

```text
local_db
enabled false
status disabled
generatedCandidates
failedCandidates
attemptedCandidates
raw payload
schema internals
fixture
mock
provider_error
UNKNOWN
MISSING
AVAILABLE
FALLBACK
STALE
```

Map necessary states into compact Chinese labels and collapse raw detail.

### 2.6 Excessive Side Gutters

Professional dashboards should use width efficiently.

Do not lock workbenches into narrow centered columns.

Use near-full workspaces for:

- Scanner
- Watchlist
- Backtest
- Market Overview
- Portfolio
- Admin/Ops tables

Narrower layouts are acceptable for:

- settings forms
- auth pages
- report drawers
- focused single-column reading views

### 2.7 All Actions Visible

Do not show every possible action at once.

Preferred pattern:

```text
primary action visible
secondary actions under 更多
destructive actions quiet and confirmed
bulk actions in command bar or footer
```

Avoid vertical action rails and button stacks.

### 2.8 Large Empty States

Empty states should not dominate the page unless the entire page is empty.

Preferred:

```text
compact empty row
one-line action hint
small inline warning
```

Avoid:

```text
large empty card slabs
multiple empty metric cards
long explanatory paragraphs
```

---

## 3. Color and Material System

### 3.1 Background

Use a calm dark graphite canvas.

Preferred:

```tsx
bg-[#050608]
bg-[#07090d]
bg-[#090b10]
bg-black
```

Avoid broad solid gray utility backgrounds:

```tsx
bg-gray-*
bg-zinc-*
bg-slate-*
bg-neutral-*
```

Use explicit graphite/black tokens or transparent overlays instead.

### 3.2 Surfaces

Surfaces should be subtle and sparse.

Primary surface:

```tsx
bg-white/[0.025] border border-white/[0.06]
```

Quiet surface:

```tsx
bg-white/[0.015] border border-white/[0.04]
```

Board/table surface:

```tsx
bg-transparent border-y border-white/[0.06]
```

Inline row hover:

```tsx
hover:bg-white/[0.035]
```

Avoid using blur as the default material. Blur should be rare and purposeful.

### 3.3 Dividers

Prefer thin dividers over nested cards.

```tsx
border-white/[0.06]
divide-white/[0.06]
```

For very quiet sections:

```tsx
border-white/[0.04]
divide-white/[0.04]
```

### 3.4 Accent Colors

Use accents sparingly.

Focus / active:

```tsx
text-blue-300
border-blue-400/30
bg-blue-400/8
```

Positive:

```tsx
text-emerald-300
```

Negative:

```tsx
text-rose-300
```

Caution:

```tsx
text-amber-300
```

Neutral:

```tsx
text-white/60
```

Do not add glow/drop-shadow by default. Financial signals should be readable, not flashy.

### 3.5 Gradients

Gradients are allowed only as subtle background depth or rare primary CTA accents.

Avoid large saturated gradients.

Do not use purple/blue Web3 gradients as the default action language.

---

## 4. Typography

### 4.1 Text Hierarchy

Use typography to create hierarchy.

Primary page title:

```tsx
text-xl md:text-2xl font-semibold tracking-tight text-white
```

Section title:

```tsx
text-sm font-medium text-white/85
```

Label:

```tsx
text-xs text-white/45
```

Micro label:

```tsx
text-[11px] text-white/40
```

Body:

```tsx
text-sm text-white/70
```

Muted metadata:

```tsx
text-xs text-white/40
```

Large decision/value:

```tsx
text-3xl md:text-4xl font-semibold tracking-tight text-white
```

Avoid excessive uppercase tracking in Chinese UI. Use it only for tiny technical labels where appropriate.

### 4.2 Mono Data

Use mono for:

- ticker symbols
- prices
- quantities
- percentages
- timestamps
- technical indicators
- IDs
- command syntax

```tsx
font-mono tracking-tight
```

Do not use mono for long Chinese prose.

### 4.3 Chinese UI Rule

Chinese pages should use Chinese labels.

Allowed English/proper nouns:

- ticker symbols: AAPL, HOOD, WULF, BTC, ETH
- provider names: Alpaca, Yahoo Finance, Binance, Finnhub, Alpha Vantage, Tushare
- indicators: MA5, MA20, RSI, MACD, VWAP, ATR, P/E, P/B, EPS, ROE
- file formats: CSV, JSON, PDF, Markdown
- currency/market codes: USD, CNY, HKD, US, HK, CN

Do not show debug English labels such as:

```text
SCANNER CANDIDATES
Key Metrics
Trade Summary
Execution Assumptions
Data Quality
UNKNOWN
MISSING
AVAILABLE
FALLBACK
STALE
```

Map them to Chinese.

### 4.4 Copy Style

Use short, operational labels.

Prefer:

```text
结论
风险
触发位
数据状态
来源
缺失字段
观察框架
证据
下一步
```

Avoid:

```text
只读观察结论
数据与来源状态说明
什么会破坏当前观察假设
当前数据质量存在以下待补充字段
```

---

## 5. Layout Architecture

### 5.1 Shell Types

Use the correct shell for the page.

| Shell | Purpose |
|---|---|
| ResearchConsoleShell | Home / single stock analysis |
| RankingBoardShell | Scanner / ranked candidates |
| DenseTableShell | Watchlist / logs / tables |
| MarketMonitorShell | Market Overview / Liquidity / Rotation |
| LedgerShell | Portfolio / transactions |
| BacktestReportShell | backtest results |
| OpsConsoleShell | admin and internal operations |

Do not make every page a bento dashboard.

### 5.2 Width Rules

Default professional workspace:

```tsx
w-full max-w-[1760px] mx-auto px-4 md:px-6 2xl:px-8
```

Board-first pages may use:

```tsx
w-full px-4 md:px-6 2xl:px-8
```

Do not create excessive side gutters at 1440px or 1920px.

### 5.3 Page Bands

Prefer page bands over card grids.

Common structure:

```text
header / command
primary task band
supporting context band
details / history / diagnostics band
```

Each band should have one reason to exist.

### 5.4 First-Fold Budget

At desktop first fold, show at most:

```text
1 primary object
1 main decision/state
1 primary action
3-5 key numbers
1 main chart/table/list
1 compact secondary context area
```

Anything else should move below or collapse.

### 5.5 Spacing Rhythm

Use consistent spacing.

Page vertical rhythm:

```tsx
space-y-6
```

Dense workbench:

```tsx
space-y-4
```

Row/table padding:

```tsx
px-3 py-2
```

Large reading/report panels:

```tsx
p-5 md:p-6
```

Avoid `p-6` on every module.

### 5.6 Forms

Label + input:

```tsx
flex flex-col gap-1.5
```

Form grid:

```tsx
grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-5
```

Do not place form controls directly adjacent without spacing.

---

## 6. Interaction Components

### 6.1 Primary Action

Primary actions should be restrained.

Use:

```tsx
bg-blue-500/90 hover:bg-blue-400 text-white border border-blue-300/20 px-4 py-2 rounded-lg transition
```

For compact contexts:

```tsx
bg-white/8 hover:bg-white/12 text-white border border-white/10 px-3 py-1.5 rounded-md text-sm transition
```

Avoid purple-blue neon gradients unless explicitly requested.

### 6.2 Secondary Button

```tsx
bg-white/[0.03] hover:bg-white/[0.06] border border-white/[0.08] text-white/70 hover:text-white px-3 py-1.5 rounded-md text-sm transition
```

### 6.3 Icon Button

```tsx
h-8 w-8 rounded-md border border-white/[0.08] bg-white/[0.025] text-white/55 hover:text-white hover:bg-white/[0.06]
```

Icon-only controls must have accessible labels.

### 6.4 Inputs

```tsx
bg-white/[0.025] border border-white/[0.08] text-sm text-white placeholder:text-white/30 px-3 py-2 rounded-lg outline-none focus:border-blue-400/40 focus:bg-white/[0.04] transition
```

With icon:

```tsx
pl-9
```

### 6.5 Selects

```tsx
appearance-none bg-white/[0.025] border border-white/[0.08] text-sm text-white px-3 py-2 pr-9 rounded-lg outline-none focus:border-blue-400/40
```

Custom arrow:

```tsx
absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-white/35
```

### 6.6 Chips

Chips must be limited.

Use chips only for:

- selected filters
- compact state
- risk/data quality tags
- category labels

Avoid chip clouds.

Compact chip:

```tsx
rounded-md border border-white/[0.08] bg-white/[0.03] px-2 py-1 text-xs text-white/60
```

### 6.7 Disclosures

Disclosures are for secondary detail, not primary layout.

Collapsed header should be thin and quiet:

```tsx
border-t border-white/[0.06] py-2 text-xs text-white/45
```

Expanded content should not become a large card grid unless necessary.

---

## 7. Data State Language

Use compact, honest states.

Chinese labels:

```text
实时
缓存
本地缓存
陈旧
备用
暂不可用
未接入
等待快照
数据不足
未知
部分可用
```

Do not mark fallback/stale/mock data as live.

Do not show repeated large red error bars.

Preferred pattern:

```text
small badge + quiet note + preserved last known good data
```

Critical warnings must remain visible, but compact.

---

## 8. Debug and Developer Details

Default UI must not expose raw debug strings.

Hide these behind collapsed sections:

```text
开发者字段
原始诊断
数据质量
执行假设
调试信息
Provider 明细
原始响应
```

Do not show by default:

```text
local_db
enabled false
status disabled
generatedCandidates
failedCandidates
attemptedCandidates
raw payload
schema internals
fixture
mock
```

Provider names are allowed only when meaningful to the user.

Admin/Ops pages may show technical detail, but still use progressive disclosure.

---

## 9. Page-Specific Guidance

### 9.1 Home / AI Analysis

Home is a Research Console, not a bento dashboard.

First fold should focus on:

```text
stock identity
stance
score
short thesis
key levels
technical structure
observation framework
```

Rules:

- No bento card grid as the primary architecture.
- No large metric-card field dump.
- No repeated diagnostics in first fold.
- Full report remains accessible but not dominant.
- Data quality remains visible but compact.
- Developer trace stays collapsed.
- Loading state should follow the same calm layout, not a noisy skeleton grid.

### 9.2 Scanner

Scanner is a Ranking Board.

First fold should focus on:

```text
scan universe
filters
ranked candidates
score
reason
primary action
```

Rules:

- Candidate pool before diagnostics.
- Candidate rows use one primary action plus `更多`.
- No left/right persistent rail.
- No vertical action stack.
- Inspector should explain:
  - 为什么入选
  - 主要风险
  - 下一步
- Raw diagnostics collapsed.

### 9.3 Watchlist

Watchlist is a Dense List.

Rules:

- Table/list is primary.
- Filters/actions compact.
- Empty state is compact.
- Batch actions should not overwhelm the primary list.
- Intelligence chips must be limited and readable.

### 9.4 Market Overview

Market Overview is a Market Monitor.

Rules:

- Regime/status first.
- Charts and ranked modules should dominate.
- Missing data must show compact unavailable states.
- Preserve cache/stale behavior.
- Crypto tab must not promote US/CN/HK indices as primary data.

### 9.5 Liquidity Monitor

Liquidity is a monitoring surface.

Rules:

- Use table/indicator rows.
- Source/runtime detail collapsed.
- Risk state visible but compact.
- Avoid large explanatory cards.

### 9.6 Rotation Radar

Rotation is a comparative board.

Rules:

- Ranked sectors/themes first.
- Selected sector detail may use a right or bottom inspector.
- Details/diagnostics collapsed.
- Avoid repeated cards for every metric.

### 9.7 Portfolio

Portfolio is a Ledger / Exposure Board.

Rules:

- P&L, exposure, risk, holdings first.
- Display currency lives in Settings, not as a large hero control.
- Native currency remains visible when FX conversion fails.
- Trade Station must not dominate the page.
- Edit/void actions must remain clear.

### 9.8 Backtest

Backtest is a Report + Chart Workspace.

First fold should focus on:

```text
strategy identity
equity curve
drawdown
core metrics
status
```

Rules:

- Do not stack dozens of cards.
- Use tabs for trades, monthly, risk, parameters, logs.
- Raw execution/data quality details collapsed.
- Metric abbreviations such as CAGR, Sharpe, Max DD may remain.

### 9.9 Options Lab

Options Lab is a hypothesis lab.

Rules:

- Hypothesis input, risk boundary, and option chain are primary.
- Data limitations remain visible but compact.
- Avoid large warning walls.
- Avoid panel sprawl.

### 9.10 Admin / Ops

Admin pages are Ops Consoles.

Rules:

- Tables/logs first.
- Detail through drawer/disclosure.
- Raw metadata allowed only in explicitly internal sections.
- Page should still feel organized, not like raw debug output.

---

## 10. Accessibility

Interactive controls should have:

- visible focus state
- accessible label when icon-only
- `aria-expanded` for disclosure buttons
- clear close button for drawers/modals
- keyboard-safe buttons where practical
- no color-only status communication where meaning is critical

Do not sacrifice usability for visual minimalism.

---

## 11. Verification Requirements

For frontend changes, run relevant tests plus:

```bash
cd apps/dsa-web
npm run build
```

For broad UI polish, run focused tests for impacted pages.

Common focused tests:

```bash
npm run test -- src/pages/__tests__/HomeSurfacePage.test.tsx --run
npm run test -- src/pages/__tests__/UserScannerPage.test.tsx --run
npm run test -- src/pages/__tests__/WatchlistPage.test.tsx --run
npm run test -- src/pages/__tests__/PortfolioPage.test.tsx --run
npm run test -- src/pages/__tests__/MarketOverviewPage.test.tsx --run
npm run test -- src/components/backtest/__tests__/BacktestResultReport.test.tsx --run
```

From repo root, run when relevant:

```bash
git diff --check
bash scripts/release_secret_scan.sh
```

If available for the task:

```bash
npm --prefix apps/dsa-web run check:design
python scripts/check_frontend_design_constitution.py
```

Browser verification must include:

- desktop 1440px
- desktop 1920px for wide workspaces
- mobile/narrow around 390px
- no horizontal overflow
- no header obstruction
- drawers/modals scroll correctly
- primary task visible above fold
- default UI has no debug strings
- no console/page errors

For visual redesigns, screenshots are required. Tests alone are not enough.

---

## 12. Commit Discipline

Before commit:

```bash
git status --short
git diff
```

Stage only files directly related to the current task.

Do not commit unrelated dirty files.

Commit message examples:

```bash
fix(ui): align home research console
fix(scanner): reduce ranking board noise
refactor(watchlist): use dense list shell
fix(portfolio): tighten exposure ledger
docs(ui): update frontend design constitution
```

---

## 13. Review Checklist

Before marking a frontend task complete, verify:

```text
Does the page have one clear primary task?
Is the first fold free of secondary diagnostics?
Are cards used only where they add grouping value?
Are debug/provider/internal fields hidden by default?
Is the layout closer to Linear-style product software than a card dashboard?
Are data warnings still honest and visible?
Are actions near the relevant data?
Is mobile usable without horizontal overflow?
Did browser verification match the intended visual direction?
```
