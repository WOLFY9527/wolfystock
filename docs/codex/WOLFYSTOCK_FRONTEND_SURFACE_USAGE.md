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
| Market Overview | `MarketMonitor` | regime strip, chart/workbench surface, ranked/comparative modules, source disclosure |
| Portfolio | `RiskConsole` / `LedgerBoard` | exposure/risk surface, holdings board, ledger rows, compact controls |
| Options Lab | `ExperimentConsole` | symbol command, assumptions, payoff/risk surface, option matrix |
| Admin/Ops | `OpsConsole` | operator status strip, queue/table, detail drawer, collapsed runbook |

## Shared Rules

- Page files own product hierarchy.
- `components/linear` owns new Linear OS material and layout primitives.
- `Terminal*` names are compatibility adapters only.
- Use one dominant surface per route.
- Prefer rows, dividers, dense lists, tables, strips, drawers, and rails before cards.
- Keep diagnostics and provider/runtime detail collapsed unless the route is explicitly admin/operator.

## Home: ResearchConsole

Required anatomy:

- wide command/search bar;
- stock identity and decision state;
- key-level strip;
- real chart workspace;
- catalyst/event rows;
- compact context rail;
- report and source drawers.

Do not perform a card/bento-first Home migration.

## Scanner: RankingBoard

Required anatomy:

- command/filter row;
- status strip;
- ranked rows or table;
- selected candidate detail;
- collapsed diagnostics/history/strategy.

Candidate rows get one primary action plus secondary disclosure. Do not turn each candidate into a mini report card.

## Watchlist: WatchBoard / DenseList

Required anatomy:

- compact add/filter row;
- dense list or table;
- status/alert strips;
- selected detail drawer or inline rail;
- compact empty rows.

## Market Overview: MarketMonitor

Required anatomy:

- regime/status strip;
- chart/workbench surface;
- ranked or comparative rows;
- collapsed source/runtime details.

Missing data must be compact and truthful.

## Portfolio: RiskConsole / LedgerBoard

Required anatomy:

- account command strip;
- exposure and P&L state;
- holdings/risk board;
- ledger/activity rows;
- secondary manual tooling.

UI work must not change accounting, FX, broker sync, or cost-basis semantics.

## Options Lab: ExperimentConsole

Required anatomy:

- symbol and status command strip;
- assumptions and risk boundary;
- payoff/risk surface;
- option chain or strategy matrix;
- collapsed data limitations.

No buy/order language unless explicitly scoped and safety-reviewed.

## Admin/Ops: OpsConsole

Admin/operator routes may be denser and more technical, but they must remain visually isolated from normal product routes.

Required anatomy:

- operator status strip;
- main queue/table/list;
- selected detail panel or drawer;
- technical details collapsed;
- danger zone isolated and confirmed.

Admin/Ops must not leak into normal user-facing route language or masthead priority.

## Browser Acceptance

For visual changes, verify:

- primary task visible above the fold;
- no horizontal overflow at desktop and mobile widths;
- 1920px workspace uses width efficiently;
- no pure-black gutters;
- no card-dashboard feel unless intentionally report/editorial;
- no raw provider/debug/schema leakage on user routes.
