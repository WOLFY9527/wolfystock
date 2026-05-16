# WolfyStock Frontend Design Constitution

WolfyStock frontend work follows the WolfyStock Linear OS design language.

Read this file before every frontend edit, then use the canonical implementation guide:

- `docs/codex/WOLFYSTOCK_LINEAR_OS_DESIGN_LANGUAGE.md`
- `docs/codex/WOLFYSTOCK_FRONTEND_SURFACE_USAGE.md`
- `docs/codex/WOLFYSTOCK_FRONTEND_ROUTE_TEMPLATES.md`
- `docs/codex/WOLFYSTOCK_TERMINAL_PRIMITIVES_USAGE.md`
- `docs/codex/WOLFYSTOCK_FRONTEND_VALIDATION_PLAYBOOK.md`

This file is the short rule set. The detailed visual contract lives in `WOLFYSTOCK_LINEAR_OS_DESIGN_LANGUAGE.md`.

## Non-Negotiable Direction

WolfyStock is a dark professional financial research OS:

- charcoal canvas, not pure-black gutters;
- slim product-first top navigation;
- wide quiet command/search bar;
- one dominant console, board, table, ledger, chart, or workbench surface per route;
- compact context rail only when the workflow needs it;
- thin separators over heavy containers;
- restrained blue active/focus state;
- green/red reserved for market semantics;
- low-noise typography and concise evidence-based copy;
- rows, tables, strips, rails, and drawers before cards.

## Forbidden Defaults

Do not use these as normal user-facing UI architecture:

- generic SaaS dashboard shells;
- admin/backend layout for product routes;
- card-first or bento-first page structures;
- widened old cards presented as a new design system;
- pure-black page islands or gutters;
- decorative material effects as routine hierarchy;
- colorful gradients as normal action language;
- helper/meta copy that says the UI is summarized, readable, trustworthy, ready, or useful.

## Surface Choice

Classify the route before editing:

- Home: `ResearchConsole`
- Scanner: `RankingBoard`
- Watchlist: `WatchBoard` or `DenseList`
- Market Overview: `MarketMonitor`
- Portfolio: `RiskConsole` or `LedgerBoard`
- Options Lab: `ExperimentConsole`
- Admin/Ops: `OpsConsole`, visually isolated from normal user-facing routes

If the route does not fit one of these, stop and document the reason before adding a new surface.

## Implementation Rule

New user-facing work should prefer:

```text
apps/dsa-web/src/components/linear/
```

Existing `Terminal*` names are compatibility exports only. They must render Linear OS material and must not define future product UI direction.

## Acceptance Gate

Frontend UI work is not done until browser verification confirms:

- no horizontal overflow at desktop and mobile widths;
- no pure-black root gutters or page gaps;
- navigation is slim and product-first;
- command/search belongs to the same charcoal system;
- the primary route surface is not a stretched old card;
- the page does not read as an admin/backend interface;
- charts and market data surfaces remain real and behaviorally unchanged;
- no raw provider/debug/schema/fixture/mock text appears on normal user routes.
