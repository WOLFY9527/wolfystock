# WolfyStock Frontend Design Constitution

WolfyStock is a Linear-inspired professional stock research operating system.

This document is mandatory for every frontend change. Before editing frontend files, read and obey this constitution. Do not invent a separate visual language unless the task explicitly scopes a prototype or design exploration.

WolfyStock should feel calm, precise, low-noise, modern, geeky, and decision-oriented. It is not a Web3 dApp, ghost-glass showcase, card-heavy dashboard, or dense admin backend.

Related docs:

- `docs/codex/WOLFYSTOCK_FRONTEND_SURFACE_USAGE.md`
- `docs/codex/WOLFYSTOCK_FRONTEND_ROUTE_TEMPLATES.md`
- `docs/codex/WOLFYSTOCK_FRONTEND_VALIDATION_PLAYBOOK.md`

---

## 0. Product Identity

The UI must feel like:

- Linear-inspired product software
- professional stock research workspace
- dark graphite canvas
- calm, minimal, precise, and restrained
- task-first, not decoration-first
- board/list/table/report-first
- data-honest, low-noise, and decision-oriented
- keyboard/command friendly
- institutional but approachable

The UI must not feel like:

- Web3 wallet/dApp interface
- crypto terminal by default
- dark Bootstrap admin panel
- generic SaaS analytics template
- card-heavy bento dashboard
- noisy quant-terminal cosplay
- developer debug console
- colorful retail finance app
- dense Web1 backend table

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

## 1. Core Principles

### 1.1 Task First

Every page must have one clear primary task.

| Page | Primary task |
|---|---|
| Home | understand one stock's current decision state |
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

WolfyStock may be dense, but only after hierarchy is clear.

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

Cards are allowed, but they are not the default.

| Task type | Preferred surface |
|---|---|
| compare candidates | ranking board / table |
| monitor assets | list / table |
| inspect one stock | research console |
| evaluate backtest | chart + report tabs |
| operate admin state | ops table + drawer |
| long-form generated analysis | report surface |

### 1.4 Progressive Disclosure

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

Expose these through disclosure rows, drawers, tabs, command palette entries, or details panels.

### 1.5 Linear-Inspired Restraint

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

Bento grids are not the default layout strategy. Bento may be used only for intentionally editorial/report-like summaries with a few high-value blocks. Do not use bento for Scanner, Backtest, Admin logs, Watchlist, or dense operations pages.

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

A page with many translucent bordered surfaces is not minimal.

### 2.4 Web3 / dApp Aesthetic

Do not use wallet/dApp visual language unless the feature explicitly requires it.

Avoid wallet chips, chain badges, purple neon, crypto glowing pills, and dApp navigation patterns.

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

Professional dashboards should use width efficiently. Do not lock workbenches into narrow centered columns. Use near-full workspaces for Scanner, Watchlist, Backtest, Market Overview, Portfolio, and Admin/Ops tables.

### 2.7 All Actions Visible

Preferred pattern:

```text
primary action visible
secondary actions under 更多
destructive actions quiet and confirmed
bulk actions in command bar or footer
```

Avoid vertical action rails and button stacks.

### 2.8 Large Empty States

Empty states should not dominate unless the entire page is empty.

Prefer compact empty rows, one-line action hints, and small inline warnings. Avoid large empty slabs, multiple empty metric cards, and long explanatory paragraphs.

### 2.9 No Meta-Explanatory UI Copy

Do not add UI copy that explains that the interface is useful, readable, trustworthy, organized, inspectable, or ready. These phrases sound like product/debug narration rather than decision information.

Forbidden examples:

```text
可信度较高
决策依据可查看
结果已整理
摘要可读
部分数据可用
未发现主要证据冲突
数据已整理
结果可查看
分析已完成
可用于观察
当前结论仅供参考
信息已汇总
摘要已生成
分析结果可查看
关键证据已整理
已完成整理
可用于决策
值得关注
```

Do not replace them with similar self-explanatory phrases.

Allowed only when backed by concrete decision data:

```text
置信度：中
数据：部分
证据：无冲突
来源：报告 / K线 / 财报
状态：已完成
```

If the phrase does not change what the user should do, remove it. Show concrete data, state, source, risk, or action instead.

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

Avoid broad utility-gray backgrounds:

```tsx
bg-gray-*
bg-zinc-*
bg-slate-*
bg-neutral-*
```

### 3.2 Surfaces

Surfaces should be subtle and sparse.

```tsx
// primary quiet surface
bg-white/[0.025] border border-white/[0.06]

// quiet surface
bg-white/[0.015] border border-white/[0.04]

// board/table surface
bg-transparent border-y border-white/[0.06]

// row hover
hover:bg-white/[0.035]
```

Avoid blur as default material.

### 3.3 Dividers

Prefer thin dividers over nested cards.

```tsx
border-white/[0.06]
divide-white/[0.06]
```

### 3.4 Accent Colors

Use accents sparingly.

```tsx
// focus / active
text-blue-300 border-blue-400/30 bg-blue-400/8

// financial states
text-emerald-300
text-rose-300
text-amber-300
text-white/60
```

Do not add glow/drop-shadow by default.

### 3.5 Gradients

Gradients are allowed only as subtle background depth or rare primary CTA accent. Do not use purple/blue Web3 gradients as default action language.

---

## 4. Typography and Copy

### 4.1 Hierarchy

```tsx
// page title
text-xl md:text-2xl font-semibold tracking-tight text-white

// section title
text-sm font-medium text-white/85

// label
text-xs text-white/45

// micro label
text-[11px] text-white/40

// body
text-sm text-white/70

// muted metadata
text-xs text-white/40

// large decision/value
text-3xl md:text-4xl font-semibold tracking-tight text-white
```

Avoid excessive uppercase tracking in Chinese UI.

### 4.2 Mono Data

Use mono for ticker symbols, prices, quantities, percentages, timestamps, technical indicators, IDs, and command syntax.

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

Map debug English labels to Chinese or collapse them.

### 4.4 Copy Style

Prefer short operational labels:

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

Avoid UI self-explanation. Show concrete data, state, source, risk, or action instead.

---

## 5. Layout Architecture

### 5.1 Shell Types

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

```text
header / command
primary task band
supporting context band
details / history / diagnostics band
```

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

```tsx
// normal page
space-y-6

// dense workbench
space-y-4

// row/table
px-3 py-2

// report panel
p-5 md:p-6
```

Avoid `p-6` on every module.

---

## 6. Interaction Components

### 6.1 Primary Action

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

### 6.4 Inputs and Selects

```tsx
bg-white/[0.025] border border-white/[0.08] text-sm text-white placeholder:text-white/30 px-3 py-2 rounded-lg outline-none focus:border-blue-400/40 focus:bg-white/[0.04] transition
```

Selects:

```tsx
appearance-none pr-9
```

Custom arrows must be `pointer-events-none`.

### 6.5 Chips

Chips must be limited to selected filters, compact state, risk/data quality tags, and category labels.

```tsx
rounded-md border border-white/[0.08] bg-white/[0.03] px-2 py-1 text-xs text-white/60
```

Avoid chip clouds.

### 6.6 Disclosures

Disclosures are for secondary detail, not primary layout.

```tsx
border-t border-white/[0.06] py-2 text-xs text-white/45
```

Expanded content should not become a large card grid unless necessary.

---

## 7. Data State Language

Use compact, honest states.

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

Preferred pattern:

```text
small badge + quiet note + preserved last known good data
```

Critical warnings must remain visible, but compact.

---

## 8. Debug and Developer Details

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

Provider names are allowed only when meaningful to the user. Admin/Ops pages may show technical detail, but still use progressive disclosure.

---

## 9. Page-Specific Guidance

### 9.1 Home / AI Analysis

Home is a Research Console, not a bento dashboard.

First fold:

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
- Data quality visible but compact.
- Developer trace collapsed.
- Loading follows the same calm layout, not a noisy skeleton grid.

### 9.2 Scanner

Scanner is a Ranking Board.

First fold:

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
- Inspector explains why included, main risk, and next step.
- Raw diagnostics collapsed.

### 9.3 Watchlist

Watchlist is a Dense List. Table/list is primary; filters/actions compact; empty state compact; batch actions should not overwhelm the list.

### 9.4 Market Overview

Market Overview is a Market Monitor. Regime/status first; charts and ranked modules dominate; missing data uses compact unavailable states; preserve cache/stale behavior.

### 9.5 Liquidity Monitor

Use table/indicator rows. Source/runtime detail collapsed. Risk state visible but compact. Avoid large explanatory cards.

### 9.6 Rotation Radar

Ranked sectors/themes first. Selected sector detail may use a right or bottom inspector. Details/diagnostics collapsed.

### 9.7 Portfolio

Portfolio is a Ledger / Exposure Board. P&L, exposure, risk, holdings first. Trade Station must not dominate the page. Native currency remains visible when FX conversion fails.

### 9.8 Backtest

Backtest is a Report + Chart Workspace. First fold: strategy identity, equity curve, drawdown, core metrics, status. Use tabs for trades, monthly, risk, parameters, logs. Calculations must not change in UI refactors.

### 9.9 Options Lab

Hypothesis input, risk boundary, and option chain are primary. Data limitations visible but compact. Avoid large warning walls and panel sprawl.

### 9.10 Admin / Ops

Tables/logs first. Detail through drawer/disclosure. Raw metadata allowed only in explicit internal sections. Keep it organized, not like raw debug output.

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

For frontend changes, run relevant tests plus build/design checks.

Common commands:

```bash
npm --prefix apps/dsa-web run build
npm --prefix apps/dsa-web run check:design
python3 scripts/check_frontend_design_constitution.py
git diff --check
bash scripts/release_secret_scan.sh
```

Browser verification for UI tasks must include:

- desktop 1440px
- desktop 1920px for wide workspaces
- mobile/narrow around 390px
- no horizontal overflow
- no header obstruction
- drawers/modals scroll correctly
- primary task visible above fold
- no debug strings
- no meta-explanatory copy
- no console/page errors

For visual redesigns, screenshots are required. Tests alone are not enough.

---

## 12. Commit Discipline

Before commit:

```bash
git status --short
git diff
```

Stage only files directly related to the task. Never use `git add .`.

Commit examples:

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
Does the page avoid meta-explanatory copy such as 可信度较高 / 决策依据可查看 / 结果已整理 / 摘要可读?
Are data warnings still honest and visible?
Are actions near the relevant data?
Is mobile usable without horizontal overflow?
Did browser verification match the intended visual direction?
```
