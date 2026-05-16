# WolfyStock Frontend Route Templates

Purpose: keep WolfyStock pages feeling like one product by classifying every route into a small set of Linear-inspired product surfaces.

Read with:

- `CODEX_FRONTEND_DESIGN_CONSTITUTION.md`
- `WOLFYSTOCK_FRONTEND_SURFACE_USAGE.md`
- `WOLFYSTOCK_FRONTEND_VALIDATION_PLAYBOOK.md`

Before editing a route, classify it below. Do not invent a new page architecture unless the task explicitly scopes a prototype.

---

## Template A: Research Console

Routes:

- 首页 / Home
- 决策台 / AI decision station
- Chat / AI research
- generated reports

Structure:

1. Compact semantic header or command/search bar.
2. Primary object identity.
3. Main decision/state.
4. Main chart/report/evidence surface.
5. Compact context rail when useful.
6. Data/source details collapsed.

Rules:

- Result/input is the hero, not onboarding copy.
- No bento card grid as the first-fold architecture.
- No tutorial wall in the first viewport.
- Evidence/debug details hidden or drawer-based.
- Financial charts must not be fake if presented as market charts.

---

## Template B: Ranking Board

Routes:

- 扫描器
- scanner results
- ranked candidates

Structure:

1. Compact command/filter bar.
2. Status strip.
3. Ranked table/list.
4. Selected detail panel or inline drawer.
5. Collapsed diagnostics/history/strategy.

Rules:

- Candidate list/table is the anchor.
- No persistent left/right rail by default.
- Controls above results, not isolated in a wasted column.
- Candidate rows use one primary action plus `更多`.
- Candidate cards must not become full mini-reports.
- Diagnostics are below/collapsed.

---

## Template C: Dense List / Table

Routes:

- 观察列表
- logs
- compact records
- entity lists

Structure:

1. Compact title/status.
2. Command/filter row.
3. Dense list/table.
4. Row actions.
5. Collapsed secondary detail.

Rules:

- Table/list first.
- Empty state compact.
- Batch actions do not dominate.
- No card slab around every row.

---

## Template D: Market Monitor

Routes:

- 市场总览
- 流动性监测
- 轮动雷达
- macro/liquidity/rotation views

Structure:

1. Regime/status strip.
2. Main market board/chart modules.
3. Ranked or comparative lists.
4. Selected detail if useful.
5. Collapsed source/runtime details.

Rules:

- Regime and primary market state first.
- Missing data compact and honest.
- Source/runtime diagnostic details collapsed.
- Crypto tab must not promote unrelated US/CN/HK indices as primary data.

---

## Template E: Ledger / Exposure Board

Routes:

- 持仓
- transactions
- cash ledger

Structure:

1. Account/exposure/P&L status.
2. Holdings/exposure board.
3. Risk and allocation.
4. Activity/ledger details.
5. Secondary manual tooling collapsed or visually secondary.

Rules:

- Portfolio accounting semantics must not change in UI work.
- Native currency remains visible when FX conversion fails.
- Display currency belongs in Settings or compact controls, not a large hero block.

---

## Template F: Backtest Report Workspace

Routes:

- 回测
- 回测结果
- strategy reports

Structure:

1. Strategy identity/status.
2. Equity curve + drawdown.
3. Core metrics strip.
4. Tabs for trades/monthly/risk/parameters/logs.
5. Raw execution/data quality collapsed.

Rules:

- Summary first, details second.
- Do not stack dozens of metric cards.
- UI refactors must not change calculations/fills/costs/metrics.

---

## Template G: Hypothesis Lab

Routes:

- 期权实验室
- strategy labs

Structure:

1. Symbol/hypothesis command area.
2. Risk boundary and assumptions.
3. Option chain / strategy matrix.
4. Payoff/risk view.
5. Data limitations collapsed.

Rules:

- Do not add trading CTAs unless explicitly scoped.
- Risk warnings compact but visible.
- No large warning walls.

---

## Template H: Ops Console

Routes:

- 控制台
- 日志中心
- 成本观测
- 证据审核
- Provider operations
- 熔断诊断
- 通知
- 用户管理
- 系统设置

Structure:

1. Operator status strip.
2. Main queue/table/list.
3. Selected detail drawer.
4. Collapsed diagnostics/runbook/schema/artifacts.
5. Isolated danger zone.

Rules:

- Diagnostics are allowed but layered.
- Chinese-first headings.
- Technical identifiers may stay as secondary metadata.
- Raw JSON/schema/runbook/payload collapsed by default.
- No secrets/tokens/Authorization/cookies.

---

## Template I: Empty / Setup

Routes/conditions:

- no holdings
- no watchlist items
- no backtest results
- no cash ledger
- no scan candidates
- no configured data source

Structure:

1. One concise state line.
2. Optional one primary action.
3. Optional short secondary action.
4. No giant warning card for harmless emptiness.

Examples:

```text
暂无持仓。添加持仓或导入交易后显示组合状态。
暂无候选。调整条件后启动扫描。
暂无现金流水。
```

---

## Global Rules

- Do not show meta-explanatory UI copy.
- Do not show raw provider/debug/schema terms in normal user flow.
- Do not make every route a card dashboard.
- The primary task must be visible above fold at 1440px.
- Mobile 390px must not horizontally overflow.
