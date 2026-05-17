# WolfyStock Linear OS Design Language

This is the canonical WolfyStock UI design language extracted from the approved WolfyStock Linear mockup.

`DESIGN.md` may be used as a historical/implementation reference, but this file is the project-specific authority for WolfyStock frontend work. If `DESIGN.md`, an installed design skill, or an older prompt conflicts with the approved mockup and this file, the mockup and this file win.

## 1. Product Principles

WolfyStock is a professional financial research operating system.

The interface should feel:

- calm, precise, and product-grade;
- data-first and decision-oriented;
- compact without becoming a backend table dump;
- broad and workspace-like, not a centered landing page;
- consistent across Home, Scanner, Watchlist, Market Overview, Portfolio, and Options Lab.

Every route has one primary workflow. Secondary data belongs in compact rails, disclosures, drawers, tabs, or lower bands.

Cards and panels are allowed when they live inside named layout regions with fixed sizing, explicit overflow behavior, and a clear information hierarchy. They are not the route structure themselves.

## 2. App Shell Anatomy

The app shell has five layers:

1. **Slim product nav**: brand, primary product routes, compact utility actions.
2. **Command row**: symbol input, route search, filters, or the primary action for the route.
3. **Main workspace**: one dominant console, board, table, chart, ledger, or workbench surface.
4. **Context layer**: compact rail, selected detail, data-quality summary, run state, or assumptions.
5. **Secondary layer**: drawers, disclosures, diagnostics, source detail, and admin-only internals.

The product UI should use the named route zones below when building Linear OS layouts:

- `HeaderStrip`
- `CommandBar`
- `PrimaryWorkRegion`
- `ContextRail`
- `SecondaryDeck`
- `DetailDrawer` / `FloatingPanel`

Normal product routes must not visually inherit admin/operator priority. Admin/Ops pages can be denser and more technical, but that density must not define the product UI.

## 3. Surface Ladder And Token Intent

Use the shared WolfyStock tokens:

| Token | Intent |
| --- | --- |
| `--wolfy-canvas` | app root canvas, charcoal and never pure black |
| `--wolfy-surface-console` | dominant console/board/workbench surface |
| `--wolfy-surface-input` | command bars, inputs, selected rows, hover states |
| `--wolfy-surface-rail` | compact rail, drawer, or secondary side surface |
| `--wolfy-border-subtle` | outer hairline borders |
| `--wolfy-divider` | row/table/section separators |
| `--wolfy-text-primary` | headings and decision-critical values |
| `--wolfy-text-secondary` | labels and secondary values |
| `--wolfy-text-muted` | timestamps, quiet hints, disabled states |
| `--wolfy-accent` | active route, focus ring, selected state |
| `--wolfy-market-up` | positive market semantics only |
| `--wolfy-market-down` | negative market semantics only |

Surfaces should step gradually from canvas to console to input/rail. Avoid detached bright panels, isolated black islands, or page-local material systems.

## 4. Typography Hierarchy

Use typography to make the decision path obvious.

- Route title: compact, semibold, not hero-sized.
- Primary object name: clear and restrained.
- Dominant decision/value: one per console; numeric values may use tabular/mono treatment.
- Section labels: 11-12 px, muted, short.
- Body copy: short, evidence-based, and decision-relevant.
- Chinese UI labels should avoid excessive uppercase tracking.

Do not add prose that says the UI is useful, readable, summarized, complete, trustworthy, or ready. Show concrete state, evidence, source, risk, or action.

## 5. Spacing And Rhythm

- Use near-full workspace width with responsive horizontal padding.
- Top nav stays slim.
- Command row is wide and quiet.
- Console padding is compact: roughly 16-24 px depending on density.
- Rows use 36-52 px height depending on data density.
- Rails use divided rows and compact groups.
- Mobile stacks into a single column without horizontal overflow.

Do not create hierarchy by adding large gaps between cards. Use dividers, rows, strips, and rails.

## 6. Linear Layout Contract

Use the layout contract below for any route that adopts the Linear OS surface model.

Desktop layout:

- `HeaderStrip` spans the route width and stays compact.
- `CommandBar` spans the route width and stays visually tied to the console surface.
- `PrimaryWorkRegion` owns the main grid track.
- `ContextRail` sits beside the primary track on desktop and uses a fixed clamp width.
- `SecondaryDeck` sits below the primary region or as a bounded lower band.
- `DetailDrawer` and `FloatingPanel` are overlays or anchored secondary surfaces, not page-wide columns.

Rail width rules:

- desktop rail width should stay in a bounded clamp, roughly 280px to 360px in the common case;
- the rail must never become a second dashboard;
- the rail drops below the primary track on mobile.

Internal scroll rules:

- only the named scroll panel or drawer should own local overflow;
- primary work regions should not rely on nested page-wide scroll containers;
- every scroll-owning region must keep `min-w-0` and a bounded height or max-height;
- content that scrolls locally must use a quiet scrollbar treatment.

Mobile stacking rules:

- command first;
- then identity and primary work;
- then key levels or other controlled strips;
- then chart or evidence workspace;
- then secondary deck;
- then rail or detail surfaces below the primary content.

Filter containment rules:

- filters belong in `CommandBar` or a compact filter bar;
- do not float filter chips outside the command row;
- do not create separate filter walls under the main workspace.

Diagnostic and detail containment rules:

- diagnostics belong in drawers, disclosures, or the context rail;
- raw provider, debug, or runtime notes stay collapsed by default;
- detail surfaces may be cards/panels, but only inside a named region with a bounded width or height.

Maximum nesting depth:

- route surface -> named region -> optional contained panel/card -> row or content leaf.
- avoid panel/card/panel/card stacks;
- one nested panel level inside a named region is the normal limit.

Expected tests:

- zone attributes exist for the main route regions;
- the rail lives inside the research console on Home and comparable research routes;
- the key-level strip and secondary deck render as controlled regions;
- the layout primitives expose fixed grid, rail, scroll, and deck behavior;
- browser tests assert the route contract instead of bento-grid or card-wall presence.

## 7. Top Nav And Command Bar Rules

Top nav:

- product routes are primary;
- active route uses restrained blue focus/underline treatment;
- utilities are compact and secondary;
- admin/operator controls do not dominate the masthead;
- no chip parade, large pill groups, or decorative nav chrome.

Command row:

- visually belongs to the same charcoal system as the page;
- input/action priority is obvious;
- filters align into the same row where space allows;
- mobile stacking must stay usable and unclipped.

## 8. ResearchConsole Anatomy

Use for Home and any focused single-stock research surface.

Required structure:

1. Command/search bar.
2. Symbol identity and decision state.
3. Score/confidence only when evidence-backed.
4. Key-level strip.
5. Real chart workspace.
6. Evidence/catalyst rows.
7. Compact context rail.
8. Full report, source detail, history, and diagnostics in drawers/disclosures.

Rules:

- chart data must be real if presented as market data;
- report gaps render neutral or empty states, never fabricated insight;
- primary decision stays visible without uncontrolled card sprawl;
- source detail remains available but not noisy.

## 9. ContextRail Anatomy

Use a context rail for selected entity detail, data quality, risk boundaries, assumptions, history, or collapsed diagnostics.

Rules:

- narrower than the main workspace;
- row-based with thin separators;
- inside the route’s dominant surface when paired with a main console;
- never becomes a second dashboard;
- moves below the primary workspace on mobile.

## 10. ChartWorkspace Rules

- Real market charts must remain real.
- Toolbar belongs to the chart surface.
- Tooltip stays within viewport bounds.
- Grid, axis, and crosshair colors follow the charcoal ladder.
- Green/red are reserved for market movement.
- No placeholder chart may replace a real chart under the same label.

## 11. Catalyst And Event Rows

Catalyst/event rows are evidence-backed and compact.

Allowed examples:

- earnings;
- regulatory events;
- rating changes;
- contracts;
- acquisitions;
- product launches;
- macro events;
- verified news.

Rules:

- no fabricated events;
- no technical/data-quality/report-summary filler in catalyst rows;
- empty state is one quiet row, for example `暂无已验证催化剂`;
- do not turn events into separate cards or decorative timelines.

## 12. Board And Table Route Rules

Use rows, tables, strips, inspectors, rails, and drawers before cards.

- Scanner: RankingBoard with command/filter strip, ranked rows/table, selected detail, collapsed diagnostics.
- Watchlist: WatchBoard/DenseList with compact add/filter, dense rows, status strips, row detail.
- Market Overview: MarketMonitor with regime strip, chart/workbench surface, ranked/comparative rows, source disclosure.
- Portfolio: RiskConsole/LedgerBoard with account strip, exposure/P&L/risk, holdings board, ledger rows.
- Options Lab: ExperimentConsole with symbol/hypothesis input, assumptions, strategy matrix, chain table, risk boundary.
- Admin/Ops: OpsConsole with status strip, queue/table/list, detail drawer, collapsed technical detail.

## 13. Forbidden Visual Patterns

These fail acceptance unless a task explicitly scopes a temporary prototype:

- pure-black root gutters or page-local black islands;
- generic SaaS dashboard template;
- user-facing admin/backend layout;
- uncontrolled card-first dashboards, card walls, and nested panel/card stacks outside named regions;
- stretched slabs created by widening old cards;
- decorative gradients, glow, heavy blur, or ornamental effects;
- fake charts or decorative market placeholders;
- raw provider/debug/schema/fixture/mock strings on normal user routes;
- helper/meta copy that explains the UI rather than presenting evidence.

## 14. UI PR Acceptance Checklist

Before landing frontend UI work:

- route surface is classified in `WOLFYSTOCK_FRONTEND_SURFACE_USAGE.md`;
- new user-facing surfaces prefer `components/linear`;
- compatibility primitives render Linear OS material;
- root canvas is charcoal, not pure black;
- nav is slim and product-first;
- command row belongs to the same surface ladder;
- one dominant workspace is visible above the fold;
- named layout zones are present where the route contract calls for them;
- rows/tables/strips/rails are used before cards;
- chart/data behavior is preserved;
- no horizontal overflow at desktop or mobile widths;
- screenshots/browser verification exist for required viewports;
- no raw internal strings or meta explanatory copy appear in normal user UI.
