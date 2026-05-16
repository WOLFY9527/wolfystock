# WolfyStock Frontend Route Templates

Purpose: keep WolfyStock pages on the Linear OS route taxonomy.

All frontend implementation tasks must classify the target route before editing. Do not add a new route template unless the task explicitly scopes a new route family.

Read with:

- `CODEX_FRONTEND_DESIGN_CONSTITUTION.md`
- `WOLFYSTOCK_LINEAR_OS_DESIGN_LANGUAGE.md`
- `WOLFYSTOCK_FRONTEND_SURFACE_USAGE.md`

## Template A: ResearchConsole

Routes:

- Home
- AI decision station
- focused single-symbol research
- generated research surfaces focused on one symbol or report

Structure:

1. Wide command/search bar.
2. Identity and decision state.
3. Key-level strip.
4. Main chart/report/evidence workspace.
5. Compact context rail when useful.
6. Data/source detail in drawer or disclosure.

Rules:

- result/input is the hero, not onboarding copy;
- chart data must be real when presented as market data;
- no card/bento-first first fold;
- no fake LLM or market content;
- no raw provider/debug detail in the primary flow.

## Template B: RankingBoard

Routes:

- Scanner
- ranked candidates
- scanner results

Structure:

1. Command/filter strip.
2. Status strip.
3. Ranked rows or table.
4. Selected detail rail/drawer.
5. Collapsed diagnostics/history/strategy.

Rules:

- candidates are the anchor;
- candidate rows get one primary action plus secondary detail;
- do not turn each candidate into a mini report card;
- controls remain close to results;
- diagnostics stay lower priority.

## Template C: WatchBoard / DenseList

Routes:

- Watchlist
- compact entity lists
- non-operator logs

Structure:

1. Compact title/status.
2. Add/filter row.
3. Dense list or table.
4. Row actions.
5. Selected detail or collapsed secondary detail.

Rules:

- list/table first;
- empty state is compact;
- batch actions do not dominate;
- no slab around every row.

## Template D: MarketMonitor

Routes:

- Market Overview
- Liquidity Monitor
- Rotation Radar
- macro/liquidity/rotation views

Structure:

1. Regime/status strip.
2. Main market board or chart workspace.
3. Ranked/comparative rows.
4. Selected detail when useful.
5. Collapsed source/runtime details.

Rules:

- regime and primary market state first;
- missing data compact and honest;
- source/runtime diagnostics collapsed;
- no unrelated indices promoted as primary data.

## Template E: RiskConsole / LedgerBoard

Routes:

- Portfolio
- transactions
- cash ledger
- exposure and risk views

Structure:

1. Account/exposure/P&L status.
2. Holdings and exposure board.
3. Risk and allocation surface.
4. Activity/ledger rows.
5. Secondary manual tooling.

Rules:

- portfolio accounting semantics must not change in UI work;
- native currency remains visible when FX conversion fails;
- display currency belongs in compact controls or settings, not a hero block.

## Template F: ExperimentConsole

Routes:

- Options Lab
- strategy labs
- hypothesis workspaces

Structure:

1. Symbol/hypothesis command area.
2. Assumptions and risk boundary.
3. Option chain or strategy matrix.
4. Payoff/risk workspace.
5. Data limitations collapsed.

Rules:

- one hypothesis at a time;
- no trading/order CTA unless explicitly scoped;
- preserve options ranking, gates, recommendation, payoff, and no-trade semantics.

## Template G: OpsConsole

Routes:

- Admin console
- Logs
- Cost observability
- Evidence review
- Provider operations
- Notifications
- Users
- System settings

Structure:

1. Operator status strip.
2. Main queue/table/list.
3. Selected detail panel or drawer.
4. Collapsed diagnostics/runbook/schema/artifacts.
5. Isolated danger zone.

Rules:

- technical detail is allowed but layered;
- raw JSON/schema/runbook details are collapsed by default;
- no secrets/tokens/cookies/Authorization headers;
- admin visual density must not define user-facing product routes.
