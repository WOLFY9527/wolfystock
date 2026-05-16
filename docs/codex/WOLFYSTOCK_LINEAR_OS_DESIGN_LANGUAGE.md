# WolfyStock Linear OS Design Language

This is the canonical WolfyStock UI design language extracted from the approved Linear OS mockup.

Use it for frontend implementation, review, and acceptance. `DESIGN.md` remains an implementation reference, but this document is the project-specific contract for WolfyStock.

## Principles

WolfyStock should feel like a calm financial research operating system:

- product software first, not marketing chrome;
- one primary workflow per route;
- dense only where density helps comparison or decision quality;
- charcoal hierarchy instead of pure-black voids;
- restrained blue for focus and active state;
- green and red only for market direction or risk semantics;
- source, provider, and debug detail available through disclosure, drawer, or admin routes;
- no filler copy, decorative gradients, glow, or glass panels.

## App Shell Anatomy

The shell has five parts:

1. Slim top nav: brand, primary product routes, compact utilities.
2. Command row: route search, symbol input, filters, or primary action.
3. Main workspace: one dominant console, board, chart, table, or workbench.
4. Context rail: compact evidence, data quality, selected detail, or run state.
5. Secondary layer: drawers, disclosures, tabs, and admin-only diagnostics.

Normal product routes must feel product-first. Admin/operator controls are secondary utilities, not the app identity.

## Surface Ladder And Token Intent

Use the shared CSS token ladder:

| Token | Intent |
| --- | --- |
| `--wolfy-canvas` | app root canvas, charcoal and never pure black |
| `--wolfy-surface-console` | dominant console/board/workbench surface |
| `--wolfy-surface-input` | command bars, inputs, row hover, selected cells |
| `--wolfy-surface-rail` | compact context rail, drawers, secondary side surfaces |
| `--wolfy-border-subtle` | outer hairlines and low-emphasis controls |
| `--wolfy-divider` | row separators and table rules |
| `--wolfy-text-primary` | headings and decision-critical text |
| `--wolfy-text-secondary` | labels, secondary values, route metadata |
| `--wolfy-text-muted` | timestamps, disabled labels, quiet hints |
| `--wolfy-accent` | active nav, focus ring, selected state |
| `--wolfy-market-up` | positive market semantics only |
| `--wolfy-market-down` | negative market semantics only |

Surfaces should move one step at a time. Avoid jumping from canvas into bright, detached cards.

## Typography Hierarchy

Use low-noise product typography:

- route title: compact, semibold, no hero scale;
- section label: 11 to 12 px, muted, normal letter spacing unless it is taxonomy;
- table/list values: 13 to 15 px, tabular numbers when possible;
- dense metrics: mono is allowed for numbers, not for every label;
- body copy: short and decision-relevant;
- no oversized H1s inside workbenches;
- no negative tracking on compact controls.

## Spacing And Rhythm

Default rhythm:

- shell safe-x: near-full width with responsive padding;
- top nav: slim, roughly one row;
- command bar: 44 to 56 px tall;
- console padding: 16 to 24 px depending on density;
- rows: 36 to 52 px depending on data density;
- rails: compact, divided by rows and strips;
- mobile: single column with no horizontal overflow.

Do not create visual rhythm through large vertical card gaps. Use dividers, strips, and row grouping.

## Top Nav And Command Bar Rules

Top nav:

- product route links are primary;
- active route uses a low-chrome blue underline or equivalent;
- utilities are compact and secondary;
- admin/operator links do not dominate the masthead;
- no chip cloud, glass button cluster, neon hover, or pill parade.

Command bar:

- belongs visually to the charcoal system;
- is wide and quiet;
- primary input/action is obvious;
- filters and secondary controls are aligned into the same row when space allows;
- on mobile, controls stack without clipping.

## ResearchConsole Anatomy

Use for Home and single-stock research.

Structure:

1. Command/search bar.
2. Identity and decision state.
3. Key level strip.
4. Chart workspace.
5. Evidence and catalyst rows.
6. Context rail with compact quality/source state.
7. Full report and source detail in drawers/disclosures.

Rules:

- chart data must be real if shown as market data;
- LLM/report gaps render neutral values, never fake insight;
- primary decision stays visible without card sprawl;
- source details remain available but not noisy.

## ContextRail Anatomy

Use a context rail for:

- selected entity details;
- data quality and freshness;
- risk boundaries;
- compact assumptions;
- related history;
- collapsed diagnostics.

Rules:

- rail is narrower than the main workspace;
- it uses row separators, not stacked cards;
- it never becomes a second dashboard;
- on mobile it moves below the primary surface.

## ChartWorkspace Rules

Chart workspaces are dominant surfaces:

- stable aspect ratio or min-height;
- no fake placeholder chart when real data is required;
- toolbar belongs to the surface, not a separate card;
- tooltip must stay within viewport bounds;
- grid, axis, and crosshair colors use the charcoal ladder;
- green/red only for market movement.

## Catalyst And Event Row Rules

Event rows should be compact and evidence-backed:

- title, date/source when available, and concise status;
- no fabricated catalysts;
- no generic event filler such as "report mainline" or "technical trigger";
- empty state is a quiet row, not a warning card.

## Board And Table Page Rules

Ranking boards, watch boards, market monitors, ledgers, and ops consoles should prefer:

- command/filter strip;
- status strip;
- dense rows or table;
- selected detail rail/drawer;
- collapsed diagnostics.

Avoid metric card grids for every minor value. A board page should scan like product software, not a landing page.

## Forbidden Visual Patterns

These fail acceptance unless explicitly scoped as a prototype:

- pure black app root, gutters, or page gaps;
- old terminal/cyber/OLED/DOS chrome;
- backdrop blur as routine panel material;
- glow or outer shadow as routine hierarchy;
- gradient CTA as default primary action;
- stretched black slabs;
- nested card stacks;
- bento as default architecture;
- admin/Web1 layout for user-facing routes;
- colorful gradient decoration;
- visible raw provider/debug/schema text on normal user routes.

## UI PR Acceptance Checklist

Before landing frontend UI work:

- route surface is classified in `WOLFYSTOCK_FRONTEND_SURFACE_USAGE.md`;
- implementation uses `components/linear` or compatibility primitives rendered with Linear material;
- root canvas is charcoal, not pure black;
- top nav is slim and product-first;
- command/search bar belongs to the same surface ladder;
- one dominant primary workspace is visible;
- rows/tables/strips/rails are used before cards;
- no glass/glow/OLED/terminal regression;
- no horizontal overflow at desktop and mobile widths;
- browser screenshots exist for required viewports;
- existing behavior, API contracts, auth, charts, and data semantics are unchanged unless explicitly scoped.
