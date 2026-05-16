# WolfyStock Frontend Surface Usage

Purpose: prevent visual drift by defining route-to-surface taxonomy for the WolfyStock Linear OS.

Read with:

- `CODEX_FRONTEND_DESIGN_CONSTITUTION.md`
- `WOLFYSTOCK_LINEAR_OS_DESIGN_LANGUAGE.md`
- `WOLFYSTOCK_FRONTEND_ROUTE_TEMPLATES.md`
- `WOLFYSTOCK_TERMINAL_PRIMITIVES_USAGE.md`

## Surface Taxonomy

| Route family | Canonical surface | Primary shape |
| --- | --- | --- |
| Home | `ResearchConsole` | command bar, decision console, chart workspace, context rail |
| Scanner | `RankingBoard` | filter/command strip, status strip, ranked rows/table, selected detail |
| Watchlist | `WatchBoard` / `DenseList` | compact add/filter, dense rows, status strips, row detail |
| Market Overview | `MarketMonitor` | regime strip, chart/workbench panels, ranked modules, source disclosure |
| Portfolio | `RiskConsole` / `LedgerBoard` | exposure/risk surface, holdings board, ledger rows, compact controls |
| Options Lab | `ExperimentConsole` | symbol command, assumptions, payoff/risk surface, option matrix |
| Admin/Ops | `OpsConsole` | operator status strip, queue/table, detail drawer, collapsed runbook |

## Shared Rules

- Page files own product hierarchy.
- `components/linear` owns new Linear OS material and layout primitives.
- `Terminal*` names are compatibility only and must render Linear OS material.
- Use one dominant surface per route.
- Prefer rows, dividers, dense lists, tables, strips, drawers, and rails before cards.
- Keep diagnostics and provider/runtime detail collapsed unless the route is explicitly admin/operator.

## Home: ResearchConsole

Use for signed-in single-stock research.

Required anatomy:

- wide command/search bar;
- stock identity and decision state;
- key level strip;
- real chart workspace;
- catalyst/event rows;
- compact context rail;
- report and source drawers.

Do not do a card/bento-first Home migration unless the task explicitly names it and the approved target requires it.

## Scanner: RankingBoard

Use for ranked candidates.

Required anatomy:

- command/filter row or rail;
- status strip;
- ranked rows or table;
- selected candidate detail;
- collapsed diagnostics/history/strategy.

Candidate rows get one primary action plus secondary disclosure. Do not turn each candidate into a full report card.

## Watchlist: WatchBoard / DenseList

Use for saved symbols and evidence monitoring.

Required anatomy:

- compact add/filter row;
- dense list or table;
- status/alert strips;
- selected detail drawer or inline rail;
- compact empty rows.

## Market Overview: MarketMonitor

Use for market regime, liquidity, and rotation views.

Required anatomy:

- regime/status strip;
- chart/workbench surface;
- ranked or comparative rows;
- collapsed source/runtime details.

Missing data must be compact and truthful.

## Portfolio: RiskConsole / LedgerBoard

Use for exposure, P&L, risk, holdings, activity, and cash ledger.

Required anatomy:

- account command strip;
- exposure and P&L state;
- holdings/risk board;
- ledger/activity rows;
- secondary manual tooling.

UI work must not change accounting, FX, broker sync, or cost-basis semantics.

## Options Lab: ExperimentConsole

Use for one options hypothesis at a time.

Required anatomy:

- symbol and status command strip;
- assumptions and risk boundary;
- payoff/risk surface;
- option chain or strategy matrix;
- collapsed data limitations.

No buy/order language unless the task explicitly scopes trading actions and safety review.

## Admin/Ops: OpsConsole

Admin and operator routes are allowed to be denser and more technical, but they must stay visually isolated from normal product routes.

Required anatomy:

- operator status strip;
- main queue/table/list;
- selected detail panel or drawer;
- raw JSON/schema/runbook collapsed;
- danger zone isolated and confirmed.

Admin/Ops must not leak into normal user-facing route language or masthead priority.

## Browser Acceptance

For visual changes, verify:

- primary task visible above fold;
- no horizontal overflow at 1440 and mobile widths;
- 1920 uses workspace width efficiently;
- no pure-black gutters;
- no card-dashboard feel unless intentionally report/editorial;
- no terminal/glass/OLED chrome;
- no raw provider/debug/schema leakage on user routes.
