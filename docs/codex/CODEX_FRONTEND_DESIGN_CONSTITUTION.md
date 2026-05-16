# WolfyStock Frontend Design Constitution

WolfyStock frontend work follows the WolfyStock Linear OS design language.

Read this file before every frontend edit, then use the canonical implementation guide:

- `docs/codex/WOLFYSTOCK_LINEAR_OS_DESIGN_LANGUAGE.md`
- `docs/codex/WOLFYSTOCK_FRONTEND_SURFACE_USAGE.md`
- `docs/codex/WOLFYSTOCK_FRONTEND_ROUTE_TEMPLATES.md`
- `docs/codex/WOLFYSTOCK_TERMINAL_PRIMITIVES_USAGE.md`
- `docs/codex/WOLFYSTOCK_FRONTEND_VALIDATION_PLAYBOOK.md`

This constitution is the short rule set. The detailed visual contract lives in `WOLFYSTOCK_LINEAR_OS_DESIGN_LANGUAGE.md`.

## Non-Negotiable Direction

WolfyStock is a dark professional financial research OS:

- charcoal canvas, not pure-black gutters;
- slim product-first top navigation;
- wide quiet command/search bar;
- one dominant console, board, table, or workbench surface per page;
- compact context rail only when the workflow needs it;
- thin separators over heavy cards;
- restrained blue active/focus state;
- green and red reserved for market semantics;
- low-noise typography and concise copy;
- rows, tables, strips, rails, and drawers before cards.

## Forbidden Defaults

Do not use these as normal WolfyStock UI architecture:

- generic SaaS dashboard shells;
- Web1/admin dashboard layout for user-facing routes;
- terminal cosplay, cyberpunk chrome, OLED glow, or old DOS language;
- ghost glass as the default panel material;
- backdrop blur on normal scrolling panels;
- pure `bg-black` or `#000000` as the root canvas;
- colorful gradients or accent decoration;
- bento/card-first layouts;
- stretched slabs and nested card stacks;
- helper/meta copy that explains the UI instead of presenting evidence.

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

New user-facing work should prefer `apps/dsa-web/src/components/linear/`.

Existing `Terminal*` names are compatibility exports only. They must render Linear OS material and must not reintroduce old terminal/glass/cyber/card chrome.

## Acceptance Gate

Frontend UI work is not done until browser verification confirms:

- no horizontal overflow at desktop and mobile widths;
- no pure-black root gutters or page gaps;
- navigation is slim and product-first;
- the command/search bar belongs to the same charcoal system;
- the primary route surface is not a stretched card slab;
- the page does not look like a generic admin dashboard;
- charts and market data surfaces remain real and behaviorally unchanged.
