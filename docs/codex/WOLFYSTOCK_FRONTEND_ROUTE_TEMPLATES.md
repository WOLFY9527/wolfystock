# WolfyStock Frontend Route Templates

Purpose: keep all WolfyStock pages feeling like one product by using a small set of route templates.

All frontend implementation tasks should classify the target route before editing.

## Template A: AI / Research

Routes:
- 首页 / Home
- 决策台 / AI decision station
- Chat / AI 研究台
- research reports

Structure:
1. Compact semantic h1 or page header.
2. Main research input/composer or result stream.
3. Context/evidence side rail only when useful.
4. Compact suggested prompts/chips.
5. Data disclaimer as one small line.

Rules:
- input/result is the hero, not onboarding copy.
- no tutorial wall in the first viewport.
- evidence/debug details are hidden or admin-only.
- page should feel like an AI research terminal, not a form.

## Template B: Market / Scanner / Watchlist

Routes:
- 扫描器
- 市场总览
- 轮动雷达
- 观察列表
- scanner results

Structure:
1. Compact semantic h1/status strip.
2. Control/filter rail or compact filter row.
3. Top-N/table/list of entities.
4. Selected detail panel or inspector.
5. Collapsed data-state/details.

Recommended desktop layout:
- scanner: left `xl:col-span-3` sticky control rail, right `xl:col-span-9` result stage
- market overview: summary/status strip + card grid with quiet per-card data badges
- rotation radar: market tabs + top-N board + selected detail + compact universe
- watchlist: compact add/filter + dense list/table

Rules:
- controls should not be buried below results.
- candidate cards should not become full mini-reports.
- use one selected detail panel instead of repeating full details in every card.
- data-state warnings should be consolidated, not repeated as amber walls.

## Template C: Portfolio / Backtest / Options

Routes:
- 持仓
- 回测
- 回测结果
- 期权实验室
- strategy report surfaces

Structure:
1. Compact result/account/symbol summary strip.
2. Main chart/table/list.
3. Risk/assumption side rail.
4. Dense detail table or ranked matrix.
5. Parameters/diagnostics/details collapsed by default.

Portfolio:
- Row 1: account command strip
- Row 2: holdings + risk
- Row 3: activity/cash + manual ledger
- manual ledger secondary/collapsed by default
- empty states compact

Backtest:
- Row 1: key metrics strip
- Row 2: chart + risk summary
- Row 3: tabs for trades/risk/parameters/diagnostics
- calculations must never change in UI refactors

Options:
- Row 1: compact symbol/status strip
- Row 2: strategy decision + assumptions + risk boundary
- Row 3: strategy matrix
- Row 4: Call/Put chains
- Row 5: collapsed assumptions/data/limitations
- risk warnings consolidated

Rules:
- summary first, details second.
- do not make every metric its own big card.
- no data-dump first viewport.
- preserve calculation/accounting semantics.

## Template D: Admin / Operator

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
3. Selected detail panel.
4. Collapsed diagnostics/runbook/schema/artifacts.
5. Danger zone for destructive actions.

Rules:
- diagnostics are allowed, but layered.
- Chinese-first headings.
- technical identifiers may stay as secondary metadata.
- raw JSON/schema/runbook/payload details collapsed by default.
- no secrets/tokens/Authorization/cookies.
- dangerous actions isolated and confirmation preserved.
- mobile must avoid endless card walls.

## Template E: Empty / Setup

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
- `暂无持仓。添加持仓或导入交易后显示组合状态。`
- `暂无候选。调整左侧条件后启动扫描。`
- `暂无现金流水。`
- `等待扫描。`

## Semantic page heading

Every routable user/admin page should expose one semantic page heading (`h1` or accessible equivalent) while keeping visual header compact.

Do not add giant hero banners just to satisfy h1.

Recommended titles:
- 首页
- 扫描器
- 决策台
- 持仓
- 市场总览
- 轮动雷达
- 观察列表
- 回测
- 期权实验室
- 设置
- 控制台
- 日志中心
- 成本观测
- 证据审核
- 数据源运维
- 通知
- 系统设置

## Width rhythm

All major routes should use the same workspace rhythm:
- `TerminalPageShell`
- `max-w-[1600px]`
- `px-4 xl:px-8`
- no page-local black slab
- no nested main-page `max-w-6xl/7xl` islands

## Page review checklist

For any route edit, verify:
- Which template does it belong to?
- Does it use Terminal primitives?
- Is semantic h1 present and compact?
- Is the first viewport useful?
- Is main action visible?
- Are warnings consolidated?
- Are empty states compact?
- Are diagnostics hidden/layered correctly?
- Does mobile stack cleanly?
