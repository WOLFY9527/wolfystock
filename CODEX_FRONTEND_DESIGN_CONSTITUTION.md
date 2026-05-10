# WolfyStock Frontend Design Constitution

WolfyStock is an ultra-minimal deep-space quantitative trading terminal for advanced traders and quants.

This document is mandatory for every frontend change. Before editing any frontend file, read and follow this design system. Do not invent visual styles outside this system unless the change explicitly explains why.

For page hierarchy, information-density budgets, and guided disclosure rules, also follow `docs/audits/frontend-information-density-and-guidance-standard.md`.
For primitive ownership and migrated-page constraints, also follow `docs/codex/WOLFYSTOCK_TERMINAL_PRIMITIVES_USAGE.md`.

---

## 0. Product Identity

WolfyStock is not a generic admin dashboard.

The UI must feel like:

- ultra-minimal deep space
- Web3-grade ghost glass
- professional quant terminal
- high-density but readable
- data-first, low-noise
- calm, dark, precise, institutional

The UI must not feel like:

- default SaaS dashboard
- Bootstrap admin panel
- gray enterprise backend
- colorful retail finance app
- noisy Web2 analytics page

---

## 1. Hard Anti-Patterns

These are forbidden in normal frontend UI code.

### 1.0 Primitive Drift

New or modified pages should use canonical Terminal primitives where applicable.

Do not invent local card, chip, button, disclosure, status, or empty-state material without a narrow justification.

For already migrated pages, do not reintroduce retired local helpers or styling bridges blocked by existing guards/tests.

### 1.1 Solid Gray Backgrounds

Do not use:

```tsx
bg-gray-*
bg-zinc-*
bg-slate-*
bg-neutral-*
```

Use transparent white or black surfaces instead:

```tsx
bg-white/[0.02]
bg-white/[0.03]
bg-black/20
bg-[#050505]
bg-black
```

### 1.2 Loud Solid Panels

Do not use fully opaque saturated backgrounds for ordinary cards or panels.

Avoid:

```tsx
bg-blue-600
bg-purple-600
bg-green-600
bg-red-600
```

Allowed only for primary CTA gradients.

Broad local gray/zinc/slate slabs and warning-wall slabs are also forbidden. Unification should happen through shared shells, spacing rhythm, typography scale, surface material, and approved primitives.

### 1.3 Native Scrollbars

Scrollable containers must use:

```tsx
overflow-y-auto no-scrollbar
```

If flex height prevents scrolling, use:

```tsx
flex-1 min-h-0
```

### 1.4 Native Form Controls

No default-looking native controls.

Select triggers must include:

```tsx
appearance-none pr-10 truncate
```

Custom select arrows must use:

```tsx
pointer-events-none
```

Checkboxes/radios should be custom-styled or wrapped in existing project primitives.

Do not leak raw/debug/provider/schema wording on normal user pages unless it is collapsed into a deliberate admin/operator disclosure.

### 1.5 Unconstrained Vertical Stacking

Complex pages must not become one endless vertical pile of cards.

Use row-based bento layout:

```tsx
grid grid-cols-1 xl:grid-cols-12 gap-6 items-start
```

Use clear page zones such as:

```text
macro row
routing row
execution row
history / secondary row
```

---

## 2. Color and Material Tokens

### 2.1 Global Background

Use:

```tsx
bg-[#050505]
bg-black
```

### 2.2 Ghost Surface

Standard card:

```tsx
bg-white/[0.02] border border-white/5 backdrop-blur-md rounded-[16px]
```

Nested inner block:

```tsx
bg-black/20 border border-white/[0.02] rounded-xl
```

Hover state:

```tsx
hover:border-white/10 hover:bg-white/[0.03] transition-all
```

### 2.3 Text Hierarchy

Core title / key metric:

```tsx
text-white
```

Normal content:

```tsx
text-white/80
```

Secondary labels / metadata:

```tsx
text-white/40
```

Disabled / unavailable:

```tsx
text-white/25
```

### 2.4 Quant Signal Colors

Bullish / buy / positive:

```tsx
text-emerald-400 drop-shadow-[0_0_8px_rgba(52,211,153,0.4)]
```

Bearish / sell / negative:

```tsx
text-rose-400 drop-shadow-[0_0_8px_rgba(251,113,133,0.4)]
```

Neutral / caution:

```tsx
text-amber-300
```

Informational / system:

```tsx
text-cyan-300
```

Do not use large saturated background blocks for these states. Prefer text, thin borders, small chips, and subtle glow.

---

## 3. Interactive Components

### 3.1 Primary CTA

Use for actions such as submit trade, run analysis, start backtest:

```tsx
bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white font-medium shadow-[0_0_15px_rgba(139,92,246,0.3)] px-6 py-2.5 rounded-lg transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed
```

### 3.2 Ghost Button

Use for cancel, settings, filters, secondary actions:

```tsx
bg-white/5 border border-white/10 text-white/70 hover:bg-white/10 hover:text-white hover:border-white/20 px-5 py-2.5 rounded-lg transition-all duration-300
```

### 3.3 Compact Ghost Button

For table rows, dense cards, and secondary inline actions:

```tsx
bg-white/[0.03] border border-white/10 text-white/60 hover:bg-white/[0.07] hover:text-white px-3 py-1.5 rounded-lg text-xs transition-all
```

### 3.4 Input / Textarea

```tsx
bg-white/[0.02] border border-white/10 text-sm text-white px-3 py-2.5 focus:border-emerald-500/50 focus:bg-white/[0.05] outline-none rounded-lg w-full transition-all
```

With icon:

```tsx
pl-10
```

### 3.5 Select / Dropdown Trigger

```tsx
bg-white/[0.02] border border-white/10 text-sm text-white px-3 py-2.5 pr-10 truncate appearance-none focus:border-emerald-500/50 focus:bg-white/[0.05] outline-none rounded-lg w-full transition-all
```

Custom arrow:

```tsx
absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-white/40
```

### 3.6 Destructive Actions

Destructive actions must not look like primary CTA.

Use quiet rose styling:

```tsx
bg-rose-500/5 border border-rose-400/20 text-rose-300 hover:bg-rose-500/10 hover:border-rose-400/30
```

Destructive actions require confirmation unless they are purely local or undoable.

---

## 4. Typography

### 4.1 Base Size

Default UI text should use:

```tsx
text-sm
```

Dense metadata may use:

```tsx
text-xs
```

### 4.2 Micro Labels

Card labels, form labels, section labels:

```tsx
text-[10px] font-bold uppercase tracking-widest text-white/40 mb-1
```

Chinese labels may still use uppercase tracking for terminal aesthetics, but avoid awkward English in Chinese routes.

### 4.3 Mono Data

Use mono for:

- ticker symbols
- prices
- quantities
- percentages
- timestamps
- terminal output
- technical indicators

```tsx
font-mono tracking-tight
```

### 4.4 Chinese UI Rule

Chinese pages should use Chinese UI labels.

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

Map them to Chinese in user-facing UI.

---

## 5. Layout Architecture

### 5.1 Global Page Wrapper

All main pages should use:

```tsx
w-full max-w-[1600px] mx-auto px-4 xl:px-8
```

Do not lock professional dashboards into narrow centered columns.

### 5.2 Bento Grid Rows

For complex dashboards:

```tsx
grid grid-cols-1 xl:grid-cols-12 gap-6 items-start
```

Common spans:

```tsx
xl:col-span-4
xl:col-span-5
xl:col-span-6
xl:col-span-7
xl:col-span-8
xl:col-span-12
```

### 5.3 Row-Based Structure

Prefer clear zones:

```text
macro row      — headline state / key summary
routing row    — decision / P&L / exposure / quality
execution row  — forms / workbench / main interaction
history row    — logs / historical records / secondary detail
```

### 5.4 Form Spacing

Label + input:

```tsx
flex flex-col gap-1.5
```

Form grid:

```tsx
grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-6 mt-6
```

Do not place form controls directly adjacent without spacing.

### 5.5 Card Padding

Compact card:

```tsx
p-3
```

Standard card:

```tsx
p-4
```

Large report/drawer card:

```tsx
p-5 md:p-6
```

Table row:

```tsx
px-3 py-2
```

Text should never touch card borders.

---

## 6. Stealth Scrolling

Use:

```tsx
overflow-y-auto no-scrollbar
```

For flex children that must scroll:

```tsx
flex-1 min-h-0 overflow-y-auto no-scrollbar
```

Never allow default visible scrollbars in primary UI.

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
```

Do not show by default:

```text
local_db
enabled false
status disabled
generatedCandidates
failedCandidates
raw payload
schema internals
fixture
mock
```

Provider names are allowed if they are meaningful to users.

---

## 9. Page-Specific Guidance

### 9.1 Home / AI Report

- Decision card should contain `完整报告` and `决策来源`.
- No placeholder company names such as `待确认股票`.
- No duplicate ticker like `TEM (TEM) (TEM)`.
- Report drawer should feel like a professional financial report.
- Developer trace stays collapsed.

### 9.2 Decision Desk

- Chinese name: `决策台`.
- Data context should show evidence status honestly.
- Provider/model names may remain English.
- No raw prompts, system prompts, API keys, or secrets.

### 9.3 Market Overview

- Tabs must remain context-aware.
- Crypto tab must not promote US/CN/HK indices as primary data.
- Missing data must show compact unavailable states.
- Preserve cache/stale behavior.

### 9.4 Scanner

- Candidate pool before diagnostics.
- Candidate rows use one primary action plus `更多`.
- Inspector should explain:
  - 为什么入选
  - 主要风险
  - 下一步
- Raw diagnostics collapsed.

### 9.5 Portfolio

- Display currency lives in Settings, not as a large hero control.
- Native currency must remain visible when FX conversion fails.
- P&L / exposure / risk should be compact.
- Trade Station must not dominate the entire page.
- Edit/void actions must remain clear.

### 9.6 Watchlist

- Intelligence chips should be readable and compact.
- Batch actions should not overwhelm the primary watchlist.
- Chinese labels by default.

### 9.7 Backtest

- Main report should read as a Chinese professional backtest report.
- Raw execution/data quality details collapsed by default.
- Metric abbreviations such as CAGR, Sharpe, Max DD may remain.

---

## 10. Accessibility

Interactive controls should have:

- visible focus state
- accessible label when icon-only
- `aria-expanded` for disclosure buttons
- clear close button for drawers/modals
- keyboard-safe buttons where practical

Do not sacrifice usability for visual minimalism.

---

## 11. Verification Requirements

For frontend changes, run relevant tests plus:

```bash
cd apps/dsa-web
npm run lint
npm run build
```

For broad UI polish, run:

```bash
npm run test -- src/pages/__tests__/HomeSurfacePage.test.tsx --run
npm run test -- src/pages/__tests__/ChatPage.test.tsx --run
npm run test -- src/pages/__tests__/MarketOverviewPage.test.tsx --run
npm run test -- src/pages/__tests__/UserScannerPage.test.tsx --run
npm run test -- src/pages/__tests__/PortfolioPage.test.tsx --run
npm run test -- src/pages/__tests__/WatchlistPage.test.tsx --run
npm run test -- src/components/backtest/__tests__/BacktestResultReport.test.tsx --run
```

Then from repo root:

```bash
./scripts/ci_gate.sh
```

Browser verification must include:

- desktop Safari or in-app browser
- mobile/narrow around 390px width
- no horizontal overflow
- no header obstruction
- drawers/modals scroll correctly
- default UI has no debug strings

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
fix(ui): polish Chinese locale and spacing
fix(scanner): improve candidate readability
fix(portfolio): repair bento layout
feat(market-overview): add relevant market depth
```
