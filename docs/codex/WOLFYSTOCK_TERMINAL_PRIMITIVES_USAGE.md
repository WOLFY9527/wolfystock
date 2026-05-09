# WolfyStock Terminal Primitives Usage

Purpose: prevent page-local visual drift by forcing shared UI primitives for page shell, panels, buttons, chips, empty states, tables/lists, and disclosures.

Use these rules after `ac982535 refactor(web): enforce terminal primitives`.

## Principle

Page files should own layout and product hierarchy.

Shared primitives should own:
- background material
- borders
- radius
- button styling
- chip/warning styling
- empty-state styling
- table/list row density
- disclosure behavior

Do not let pages repeatedly hand-roll:

```text
bg-white/[0.02]
border-white/5
rounded-[16px]
gradient CTA
yellow warning badges
custom empty cards
```

## Expected primitive module

Prefer existing project primitives under:

```text
apps/dsa-web/src/components/terminal/
```

Expected exports may include:

- `TerminalPageShell`
- `TerminalGrid`
- `TerminalPanel`
- `TerminalNestedBlock`
- `TerminalSectionHeader`
- `TerminalMetric`
- `TerminalButton`
- `TerminalChip`
- `TerminalEmptyState`
- `TerminalNotice`
- `TerminalDenseList`
- `TerminalDenseTable`
- `TerminalDisclosure`

Do not create competing primitives unless the existing primitive cannot support the task.

## TerminalPageShell

Use for normal page root.

Target behavior:
- `w-full`
- `max-w-[1600px]`
- `mx-auto`
- `px-4 xl:px-8`
- `flex flex-col gap-6`
- no local solid background
- no local black slab

Forbidden page-root patterns:
- `bg-black`
- `bg-[#000]`
- `bg-[#050505]`
- `bg-gray-*`
- `bg-zinc-*`
- `bg-slate-*`
- `bg-neutral-*`
- `max-w-5xl`, `max-w-6xl`, `max-w-7xl` as main page shell
- extra centered island wrappers around the entire page

## TerminalGrid

Use for complex 12-column layouts.

Target behavior:
- `grid grid-cols-1 xl:grid-cols-12 gap-6 items-start`
- page layout only
- mobile stacks cleanly

## TerminalPanel

Use for major panels.

Target material:
- `bg-white/[0.02]`
- `border border-white/5`
- `backdrop-blur-md`
- `rounded-[16px]`
- `p-5` default
- dense variant may use `p-4`

Avoid:
- fully opaque black panels
- solid gray panels
- nested card overload

## TerminalNestedBlock

Use for compact inner blocks.

Target material:
- `bg-black/20`
- `border border-white/[0.02]`
- `rounded-xl`
- `p-3`

Nested blocks are allowed. Page-level black slabs are not.

## TerminalSectionHeader

Use compact section headings.

Expected hierarchy:
- eyebrow: `text-[10px] font-bold uppercase tracking-widest text-white/40`
- title: `text-sm` or `text-base`, `font-medium`, `text-white/90`
- optional action slot
- no long explainer paragraphs

## TerminalMetric

Use for numeric summary cells.

Rules:
- label: `text-[10px] uppercase tracking-widest text-white/35`
- value: `font-mono tracking-tight text-white`
- subvalue: `text-xs text-white/35`
- compact cell material through primitive, not page-local classes

Use for:
- portfolio totals
- scanner counts
- provider status numbers
- backtest metrics
- market overview summary values

## TerminalButton

Use variants instead of page-local button classes.

Expected variants:
- `primary`: blue-purple gradient CTA for the single main action
- `secondary`: ghost button
- `compact`: dense row/action button
- `danger`: quiet rose destructive action

Rules:
- One page should not have many unrelated button styles.
- Use `primary` only for true main CTA.
- Do not invent random green/gray/cyan button fills inside pages.
- Do not use native-looking buttons.

## TerminalChip

Use variants for all statuses.

Expected variants:
- `neutral`
- `success`
- `caution`
- `danger`
- `info`

Rules:
- No loud solid yellow/brown tags.
- Data state should be quiet and honest.
- Risk/prohibit uses `danger`.
- Caution uses low-opacity amber.
- Info uses cyan.
- Success uses emerald.
- Raw internal reason codes must not appear on normal user pages.

## TerminalEmptyState

Use for harmless empty states.

Rules:
- compact height, normally `min-h-[72px]` to `min-h-[100px]`
- low contrast text
- one concise line
- optional action slot
- no giant warning icon for harmless empty state

Good examples:
- `暂无持仓。添加持仓或导入交易后显示组合状态。`
- `暂无现金流水。`
- `等待扫描。`
- `暂无候选。调整左侧条件后启动扫描。`

## TerminalNotice

Use for compact warnings and data states.

Rules:
- preserve honest warnings
- do not repeat the same warning in every card
- consolidate shared warnings into one strip or side panel
- user-facing copy must be Chinese-first

## TerminalDisclosure

Use for advanced details.

Normal user pages:
- do not show developer/debug entry points unless product explicitly requires it

Admin/operator pages:
- raw JSON/schema/runbook/provider traces may exist but should be collapsed/lower priority
- never show secrets/tokens/cookies/Authorization headers

## Page-file rules

In migrated pages, local `className` should be used mainly for:
- grid columns
- flex layout
- gap
- responsive ordering
- width constraints inside specific sections

Avoid local material classes for:
- panels
- chips
- primary buttons
- empty states
- notices
- dense table rows

## User-facing forbidden terms

Normal user pages must not visibly render:

- `开发者详情`
- `developer`
- `debug`
- `raw`
- `schema`
- `trace`
- `provider_timeout`
- `not_enough_history`
- `fundamentals_unavailable`
- `optional_news_timeout`
- raw English `fallback`
- raw English `dry run`
- `LLM Ledger`
- `QUOTA PILOT`
- `MarketCache`
- `local_db`
- `generatedCandidates`
- `failedCandidates`
- `fixture`
- `mock`

Use Chinese equivalents:
- `数据不足`
- `历史数据不足`
- `部分外部数据暂不可用`
- `仅供观察`
- `需人工复核`
- `依据需复核`
- `当前未满足条件`
- `暂无数据`

## Admin/operator exception

Admin/operator pages may show technical diagnostics, but:
- primary heading should be Chinese-first
- technical strings should be secondary
- raw details should be in `TerminalDisclosure`
- dangerous actions need isolated danger zones
- no secrets/tokens/credentials should ever render

## Design guard

The Python/JS design guard should be used to catch:
- local page slabs
- solid gray/zinc/slate/neutral backgrounds
- loud warning slabs
- visible internal terms on user pages
- unstyled native controls
- migrated pages not using terminal primitives
