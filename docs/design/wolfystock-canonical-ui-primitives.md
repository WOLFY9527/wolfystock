# WolfyStock Canonical UI Primitives

Status: Linear OS aligned replacement for the older primitive-governance note.  
Repository: `/Users/yehengli/daily_stock_analysis`  
Intended path: `docs/design/wolfystock-canonical-ui-primitives.md`

## 1. Purpose

This document is useful and should be kept after replacement.

Its job is to explain which UI primitives should own WolfyStock product surfaces after the Linear OS foundation. It is not a competing visual system. It must defer to:

```text
docs/codex/WOLFYSTOCK_LINEAR_OS_DESIGN_LANGUAGE.md
docs/codex/WOLFYSTOCK_FRONTEND_SURFACE_USAGE.md
docs/codex/WOLFYSTOCK_FRONTEND_ROUTE_TEMPLATES.md
docs/codex/CODEX_FRONTEND_DESIGN_CONSTITUTION.md
```

Primary rule:

```text
New user-facing surfaces should prefer apps/dsa-web/src/components/linear/.
```

Older common or compatibility components may remain while routes migrate, but they must not define the future product UI direction.

## 2. Linear OS Primitive Principles

WolfyStock primitives should encode:

- charcoal surface ladder;
- one dominant console/board/workbench per route;
- thin separators and row grouping;
- compact command/filter rhythm;
- compact context rail when useful;
- evidence-first copy;
- real chart/table/data behavior;
- mobile without horizontal overflow;
- raw diagnostics collapsed by default.

They should not encode:

- card-first page architecture;
- route-local material styling;
- decorative material effects as hierarchy;
- widened old cards presented as a new design system;
- product-route admin/backend layout;
- helper copy that says the UI is summarized, readable, trustworthy, ready, or useful.

## 3. Canonical Surface Taxonomy

| Route family | Surface | Primary shape |
| --- | --- | --- |
| Home | `ResearchConsole` | command bar, decision console, chart workspace, compact context rail |
| Scanner | `RankingBoard` | filter strip, status strip, ranked rows/table, selected detail |
| Watchlist | `WatchBoard` / `DenseList` | compact add/filter row, dense rows, row detail |
| Market Overview | `MarketMonitor` | regime strip, chart/workbench panels, comparative rows, source disclosure |
| Portfolio | `RiskConsole` / `LedgerBoard` | exposure/risk surface, holdings board, ledger rows |
| Options Lab | `ExperimentConsole` | symbol command, assumptions, payoff/risk surface, option matrix |
| Admin/Ops | `OpsConsole` | operator status strip, queue/table, detail drawer, collapsed diagnostics |

## 4. Primitive Ownership

### 4.1 App and route shell

Use the application shell for root canvas, route width, scroll ownership, masthead rhythm, and app-level navigation.

Rules:

- root canvas uses the shared charcoal ladder;
- product navigation is slim and product-first;
- admin/operator controls are secondary;
- no route-local full-page black island;
- no narrow centered island for workbench pages.

Tests:

- `Shell.test.tsx`;
- route-specific browser proof at desktop and mobile widths.

### 4.2 `WolfyCommandBar`

Purpose:

- symbol input;
- global route command;
- compact filters;
- primary workflow action.

Rules:

- visually belongs to the same charcoal system as the route surface;
- does not become a chip cloud;
- one primary action is visible; secondary controls are compact;
- mobile stacks without clipping.

### 4.3 `ResearchConsoleShell`

Purpose:

- Home and one-symbol research;
- one dominant decision surface;
- left research workspace plus compact right rail.

Required anatomy:

1. identity and ticker;
2. stance/score/confidence;
3. short thesis;
4. key-level strip;
5. chart workspace;
6. context rail;
7. event/catalyst rows;
8. report/source drawers.

Rules:

- real market chart if market chart is shown;
- no bento-first first fold;
- no fake catalysts;
- no repeated data-quality paragraphs.

### 4.4 `ConsoleBoard`

Purpose:

- primary route work surface for boards, tables, charts, and reports.

Rules:

- one board per route first fold;
- use row sections, dividers, and strips;
- do not nest many independent containers;
- secondary details move to drawers, disclosures, rails, or below-fold sections.

### 4.5 `ConsoleContextRail`

Purpose:

- selected entity detail;
- observation framework;
- data quality/source state;
- risk boundaries;
- current assumptions;
- compact follow-up state.

Rules:

- rail is narrower than the workspace;
- desktop uses an internal separator;
- mobile stacks below primary board;
- rows and thin dividers before stacked containers.

### 4.6 `ConsoleStatusStrip`

Purpose:

- compact status/count/freshness row;
- not a hero metrics wall.

Rules:

- 3 to 6 concise cells;
- label/value/detail pattern;
- market green/red only when it means market movement or risk;
- no filler labels.

### 4.7 `KeyLevelStrip`

Purpose:

- trading/research levels such as trigger, invalidation, next focus.

Rules:

- horizontal strip on desktop;
- stacked compact rows on mobile;
- exactly data/evidence labels;
- no generic confidence prose.

### 4.8 `ChartWorkspace`

Purpose:

- candlestick, market chart, backtest equity curve, regime chart, or payoff chart.

Rules:

- chart is real when the UI claims market data;
- controls are part of the chart surface;
- tooltip stays in viewport;
- no placeholder SVG pretending to be market data;
- axis/grid colors use the charcoal ladder.

### 4.9 `CatalystRows`

Purpose:

- verified event/catalyst rows.

Rules:

- compact row grid;
- max visible rows unless route explicitly needs more;
- empty state is one quiet row;
- exclude technical filler and report-summary filler.

### 4.10 `DataWorkbenchFrame`

Purpose:

- Scanner, Watchlist, MarketMonitor, Portfolio, Admin/Ops tables.

Rules:

- table/list/rows first;
- one primary row action plus secondary detail;
- dense but readable;
- selected detail via rail/drawer/disclosure;
- no horizontal overflow on mobile.

### 4.11 `DenseRows`

Purpose:

- dense list and table row primitives.

Rules:

- stable row height;
- clear selected/hover states;
- compact status cells;
- row actions near context;
- mobile row conversion must preserve labels.

### 4.12 `ConsoleDisclosure`

Purpose:

- secondary details, raw diagnostics, source traces, provider notes, and admin runbooks.

Rules:

- collapsed by default for normal product routes;
- sanitized content;
- no secrets;
- raw provider/schema/debug details never in primary user UI.

## 5. Inputs And Actions

Use existing shared input/action components only if they already follow the Linear OS material and accessibility requirements.

Requirements:

- visible focus state;
- accessible labels for icon-only controls;
- native semantics preserved where useful;
- compact but not unusable on mobile;
- Chinese-first UI labels on Chinese routes.

Avoid introducing page-local variants for:

- buttons;
- chips;
- inputs;
- selects;
- checkboxes;
- toggles;
- empty states;
- notices;
- disclosures;
- table rows.

If a route needs a new primitive, add it to `components/linear` with focused tests and explain why existing primitives were insufficient.

## 6. Domain Adapter Rules

Shared primitives own visual shape. Domain adapters own meaning.

Examples:

| Domain | Adapter owns |
| --- | --- |
| Market provider/freshness | freshness, fallback, stale, provider health, cache state |
| Scanner | candidate state, ranking context, run lifecycle |
| Watchlist | saved-symbol intelligence, batch state |
| Backtest | verdicts, data quality, execution assumptions |
| Portfolio | accounting, FX transparency, broker state, risk |
| Options Lab | hypothesis, gates, no-trade conditions, payoff/risk |
| Admin/Ops | severity, operator run state, diagnostics |

Do not create one giant cross-domain enum. It erases meaning and creates unsafe coupling.

## 7. Migration Strategy

Stage 0: foundation and docs are already established.

Stage 1: Home golden route.

- use `ResearchConsoleShell`;
- remove bento-first first fold;
- preserve real chart and analysis behavior;
- make Home the visual acceptance reference.

Stage 2: low-risk board/list pages.

- Scanner -> `RankingBoard`;
- Watchlist -> `WatchBoard` / `DenseList`;
- run in parallel only if they do not edit shared primitives.

Stage 3: Market Overview.

- migrate to `MarketMonitor`;
- keep provider/freshness semantics honest;
- collapse runtime details.

Stage 4: high-coupling pages.

- Portfolio -> `RiskConsole` / `LedgerBoard`;
- Options Lab -> `ExperimentConsole`;
- handle serially due to behavior/test coupling.

Stage 5: Admin/Ops containment.

- use `OpsConsole`;
- allow technical density, but isolate it from normal product routes.

## 8. First Recommended Tasks

| Task | Scope | Parallel safety |
| --- | --- | --- |
| Home ResearchConsole golden route | Home first fold and report/source drawers | serial |
| Scanner board migration | ranking rows and selected detail | parallel after Home acceptance |
| Watchlist board migration | dense saved-symbol rows and batch actions | parallel after Home acceptance |
| MarketMonitor pass | regime/chart/row workbench | after board primitives stabilize |
| Portfolio RiskConsole pass | exposure/holdings/ledger/risk | serial |
| Options ExperimentConsole pass | hypothesis/strategy/chain/payoff | serial |
| Admin/Ops visual containment | admin routes only | later |

## 9. Prompt Snippet

Use this in future frontend prompts:

```text
Read:
- docs/codex/WOLFYSTOCK_LINEAR_OS_DESIGN_LANGUAGE.md
- docs/codex/WOLFYSTOCK_FRONTEND_SURFACE_USAGE.md
- docs/codex/WOLFYSTOCK_FRONTEND_ROUTE_TEMPLATES.md
- docs/design/wolfystock-canonical-ui-primitives.md

Use components/linear for new user-facing surfaces. Do not create page-local visual material. Shared primitives own surface, density, border, radius, disclosure, and row rhythm. Domain adapters own semantics. If existing common or compatibility components are used, they must render Linear OS material and must not define future product UI direction.
```

## 10. Acceptance Checklist

Before a frontend task is complete:

- route surface is classified;
- primary route surface is clear in the first viewport;
- command/filter area belongs to the same charcoal system;
- no page-local pure-black islands;
- no widened old cards as a new design system;
- chart/data surfaces remain real;
- row/table/list surfaces remain scannable;
- context rail is compact when present;
- raw diagnostics are collapsed;
- no forbidden meta copy appears;
- mobile has no horizontal overflow;
- browser screenshots are fresh captures from current HEAD, not old reference files.
