# WolfyStock Frontend Surface Usage

Purpose: prevent visual drift by defining the approved Linear-inspired page surfaces and shared UI vocabulary.

This replaces the old ghost-glass/terminal-card-first guidance. Existing `Terminal*` primitives may still be used when they comply with the current design constitution, but they are not a license to reintroduce card-heavy dashboards.

Read with:

- `CODEX_FRONTEND_DESIGN_CONSTITUTION.md`
- `WOLFYSTOCK_FRONTEND_ROUTE_TEMPLATES.md`
- `WOLFYSTOCK_FRONTEND_VALIDATION_PLAYBOOK.md`

---

## 1. Principle

Page files own product hierarchy.

Shared primitives own:

- page shell rhythm
- board/list/table surface material
- button/chip/disclosure styling
- empty-state density
- drawer/disclosure behavior
- data-state visual language

Do not hand-roll local panels, chips, buttons, disclosures, warnings, or empty states unless the existing primitive cannot support the task. Explain any new primitive in the final report.

---

## 2. Approved Surface Types

### 2.1 ResearchConsole

Use for Home and single-stock analysis.

Structure:

```text
compact command/search
stock identity + stance + score
key levels strip
main chart / evidence
right context rail
events / catalysts
collapsed data/source details
```

Rules:

- No bento grid as first fold.
- Technical chart must be real when claimed as market chart.
- Data quality visible but compact.
- Report/source details in drawer/disclosure.

### 2.2 RankingBoard

Use for Scanner and ranked candidates.

Structure:

```text
compact command/filter bar
status strip
ranked table/list
selected detail
collapsed diagnostics/history/strategy
```

Rules:

- Ranked candidates are the anchor.
- One primary row action plus `更多`.
- No persistent side rails by default.
- No vertical action stack.
- Rejected/failed candidates available through filters or disclosures, not first-fold noise.

### 2.3 DenseList

Use for Watchlist, logs, compact entities.

Rules:

- List/table first.
- Header and filters compact.
- Empty state is an inline row.
- Secondary diagnostics collapsed.

### 2.4 MarketMonitor

Use for Market Overview, Liquidity, Rotation Radar.

Rules:

- Regime/status first.
- Charts and ranked modules dominate.
- Source/runtime details collapsed.
- Missing data compact and honest.

### 2.5 LedgerBoard

Use for Portfolio and transaction/accounting views.

Rules:

- Exposure, P&L, holdings, and risk first.
- Ledger/actions secondary.
- Accounting semantics must not change in UI work.

### 2.6 BacktestReport

Use for backtest result surfaces.

Rules:

- Equity curve/drawdown/core metrics first.
- Trades/risk/parameters/logs through tabs.
- Raw execution/data quality collapsed.
- UI refactors must not change calculation semantics.

### 2.7 OpsConsole

Use for Admin/Ops.

Rules:

- Status strip + main table/queue first.
- Details through drawer/disclosure.
- Raw JSON/schema/runbook collapsed.
- Danger zone isolated and confirmed.

---

## 3. Primitive Guidance

### 3.1 Prefer Thin Structures

Prefer:

```text
section rows
dividers
tables/lists
compact strips
drawers
disclosures
```

Avoid:

```text
TerminalPanel around every group
nested glass cards
large metric card grids
warning card walls
chip clouds
```

### 3.2 Existing Terminal Primitives

Existing `Terminal*` primitives may be used only when they match current constitution:

- `TerminalButton` can be reused if visually restrained.
- `TerminalChip` can be reused when chips are limited and meaningful.
- `TerminalDisclosure` can be reused for secondary details.
- `TerminalDenseTable/List` can be reused for table/list pages.
- `TerminalPanel` should be used sparingly, not as the default page-building block.
- `TerminalMetric` should not become a large card grid for minor values.

If a primitive still hard-codes old ghost-glass/card-heavy styling, prefer a task-scoped additive primitive or update the primitive only when explicitly scoped.

### 3.3 Dense Workbench Primitives

Approved dense primitives may include:

```text
DensePageHeader
DenseStatusStrip
DenseCommandBar
DenseTableShell
DenseTableFrame
CompactEmptyRow
DenseSecondaryDisclosure
```

Use them for table/list/board pages where appropriate.

---

## 4. Styling Rules

- Use dark graphite backgrounds.
- Use thin dividers over heavy cards.
- Use restrained blue for focus/active.
- Use green/red only for financial meaning.
- Avoid glow, blur, neon gradients, and decorative panels.
- Avoid broad gray/zinc/slate/neutral slabs.
- Avoid native-looking controls.
- Avoid default visible scrollbars in primary app UI.

---

## 5. Copy Rules

- Use Chinese labels on Chinese pages.
- Collapse raw provider/schema/debug details.
- Do not add meta-explanatory copy such as `可信度较高`, `决策依据可查看`, `结果已整理`, `摘要可读`.
- Replace with concrete data only when decision-relevant.

---

## 6. Browser Acceptance

For UI surface changes, verify:

- primary task visible above fold;
- no horizontal overflow at 1440 and 390;
- 1920 uses width efficiently;
- no card-dashboard feel unless intentionally report/editorial;
- secondary details collapsed by default;
- no raw debug/provider/schema leakage;
- no meta-explanatory UI copy;
- screenshots match task visual direction.
