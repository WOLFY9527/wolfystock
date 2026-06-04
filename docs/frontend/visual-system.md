# WolfyStock Frontend Visual System

Status: current frontend visual and primitive authority.

Reference image: `docs/design/reference/wolfystock-reflect-linear-home-mockup.png`.

This document consolidates the former Reflect-Linear design language, frontend
design constitution, route surface usage, route templates, terminal primitive
compatibility note, and canonical UI primitive policy. Older deep-space,
ghost-glass, OLED terminal, bento-first, card-first, or generic Linear-only
wording is historical unless this file keeps the rule explicitly.

## Design Thesis

WolfyStock is a professional financial research OS. The interface should feel
calm, precise, low-key, premium, data-rich, and decision-oriented. The visual
language combines:

- Reflect atmosphere: dark canvas, muted violet glow, subtle glass, fine
  borders, micro-noise, and refined depth.
- Linear discipline: strong alignment, fixed regions, restrained color,
  predictable product ergonomics, and low chrome.
- Financial seriousness: compact charts, rows, evidence, risk, freshness, and
  uncertainty without trading-game or crypto-casino energy.

Avoid cheap neon, high-saturation purple, marketing hero layouts, decorative
3D, dashboard-kit card mosaics, auto-height masonry, uncontrolled nested
panels, and developer-looking raw `Details` labels in product surfaces.

## Visual Tokens

Use a dark charcoal-to-midnight-navy ladder rather than flat pure black as the
only canvas.

| Token intent | Rule |
| --- | --- |
| Root canvas | Near-black navy with very low chroma |
| Shell canvas | Dark charcoal-navy |
| Console surface | Translucent midnight panel |
| Panel surface | Slightly lifted dark glass |
| Inset surface | Deeper chart/table well |
| Border | Hairline cool gray-violet |
| Primary accent | Muted low-saturation violet |
| Secondary accent | Restrained cool blue-violet |
| Market green/red | Reserved for financial semantics |
| Warning amber | Rare, only for risk or availability states |

Purple is atmosphere and interaction emphasis, not decoration. Green and red
must stay market-semantic: gain/loss, bullish/bearish, valid/invalid risk
states, or equivalent domain meaning.

## Typography And Density

- Preferred family: Inter, SF Pro, or system sans-serif.
- Use tabular numerals for financial numbers where possible.
- Keep headings clear but restrained; reserve hero-scale type for a true
  primary surface.
- Use compact labels and high-information rows instead of filler paragraphs.
- Beginner copy should explain uncertainty and terms without buy/sell/order
  wording.

Suggested scale intent:

| Surface | Size intent |
| --- | --- |
| Nav / utility | 12-13px |
| Labels | 11-12px, muted |
| Body / rows | 13-14px |
| Metric values | 20-36px by importance |
| Page title | 22-30px |
| Hero stance value | 32-42px only when it anchors the surface |

## Region Contract

Every major route should declare its layout regions before placing content.
Cards and panels are allowed only inside predefined regions with fixed sizing,
explicit overflow behavior, and a clear hierarchy.

Default skeleton:

```text
TopNavigation
CommandBar or HeaderStrip
RouteConsole
  PrimaryWorkRegion
  ContextRail or FloatingDetailPanel
  SecondaryDeck
```

Core surface ladder:

```text
AppCanvas
  ShellBar
  CommandBar
  ResearchConsole / RouteConsole
    PrimaryWorkRegion
      ChartWell / DataTableWell
      MetricStrip / KeyLevelStrip
    ContextRail
    SecondaryDeck
      DataRows / EventRows
    FloatingDetailPanel / Drawer
```

Maximum default visible nesting depth is 2. Long secondary content should be
collapsed, internally scrollable, or moved to a drawer/floating panel.

## Route Surface Taxonomy

| Route family | Surface | Primary region | Secondary / rail |
| --- | --- | --- | --- |
| Home | ResearchConsole | Stock thesis, score, key levels, chart | Observation rail and catalysts |
| Scanner | RankingBoard | Candidate rows/table | Selected-candidate rail and collapsed diagnostics |
| Watchlist | WatchBoard | Watch rows/list | Compact filters and bounded detail |
| Chat | ResearchWorkspace | Conversation and composer | Evidence/context rail |
| Market Overview | MarketMonitor | Market state and comparative boards | Freshness/source rail |
| Liquidity | LiquidityMonitor | Liquidity score and signal table | Source/risk rail |
| Rotation Radar | RotationMonitor | Ranked themes/sectors | Selected theme detail rail |
| Portfolio | RiskConsole / LedgerBoard | Holdings ledger | Risk/activity rail |
| Options Lab | ExperimentConsole | Scenario/strategy decision board | Risk boundary rail |
| Backtest | ResearchRunConsole | Result/compare workspace | Parameters/details drawer |
| Admin/Ops | OpsConsole | Operations table/queue | Status/actions rail |
| Settings | PreferenceConsole | Settings rows | Help/details rail |

Screenshot acceptance: the first viewport must reveal the route's primary task.
If filters, diagnostics, empty panels, or card stacks dominate the first
viewport, the route fails.

## Route Template Requirements

Home must show one dominant ResearchConsole with command bar, company identity,
current research stance, score/confidence/data-quality state, key levels, a
visually dominant chart, fixed context rail, and attached catalyst/event deck.

Scanner and Watchlist must lead with rows/lists, not filter slabs. Scanner
diagnostics, backtest, and comparison evidence are collapsed by default.

Chat must use a bounded conversation scroll panel, anchored composer, and a
bounded or collapsed evidence rail.

Market Overview, Liquidity, and Rotation must lead with market state and
comparative boards. Source/freshness detail stays in a rail or disclosure.

Portfolio must put holdings, P&L, exposure, FX/read-only sync state, and ledger
truth before manual forms. Do not imply broker order execution by default.

Options Lab must start with scenario readiness, data sufficiency, and no-advice
framing before chain, Greeks, or strategy detail.

Backtest must lead with result, risk metrics, assumptions, and evidence quality
before export, rerun, trace, ledger, and raw data-quality controls.

Admin/Ops may be denser than user routes, but still starts with operator state,
impact, recommended operator action, evidence, then raw details.

## Information Architecture

Launch-facing routes should default to this order:

1. Page intent.
2. Current state: live, cached, partial, stale, unavailable, or waiting.
3. Primary user question.
4. Recommended safe next step: observe, inspect evidence, refine filters,
   compare scenarios, export, or wait for data.
5. Evidence summary.
6. Details and diagnostics.

Raw provider/cache/schema/debug terms are Level 3 diagnostics and should stay
collapsed by default on user routes. Risk and uncertainty must remain visible
near the conclusion; never hide uncertainty behind a green badge.

## Guided Help And Copy

No shared glossary/help registry is currently active in `apps/dsa-web/src`.
Keep user-facing explanations close to the owning surface and reuse existing
disclosure or inline helper patterns for interpretation-critical content.
Tooltips explain terms; they must not contain workflow steps, blocking
warnings, raw diagnostics, or long policy copy.

Visible glossary triggers should stay below 5 per desktop viewport and 3 per
mobile viewport. Do not place tooltips on every table cell.

## Primitive Ownership

New user-facing surfaces should prefer:

```text
apps/dsa-web/src/components/linear/
```

Existing `Terminal*` exports are compatibility adapter names only. They must
render Reflect-Linear material and must not justify new terminal/cosplay
architecture.

Layout primitives own geometry, overflow, and responsive stacking:

- `FixedRegionGrid`
- `PrimaryWorkRegion`
- `ContextRail` / `RailPanel`
- `SecondaryDeck`
- `ScrollPanel`
- `FloatingDetailPanel`
- `Drawer`

Surface primitives own tone, border, blur, and glow:

- `ResearchConsole`
- `RouteConsole`
- `GlassPanel`
- `ChartWell`
- `InsetSurface`

Data primitives prevent card-per-item repetition:

- `MetricStrip`
- `KeyLevelStrip`
- `DataRows`
- `EventRows`
- `SignalRows`
- `CompactTable`

Control primitives prevent filter and toolbar sprawl:

- `CommandBar`
- `CompactFilterBar`
- `SegmentedControl`
- `IconAction`
- `UtilityMenu`

Page files own route-specific hierarchy, grid ratios, data mapping, product
copy, behavior, and state orchestration. Shared primitives own material,
radius, border, row density, button/chip/notice/empty/disclosure styling,
command rhythm, and rail rhythm.

## Acceptance Checklist

A frontend route passes only if:

- fixed named regions are visible in structure and screenshot;
- the primary work region appears in the first viewport;
- filters are compact;
- rail/detail content is bounded, collapsed, or internally scrollable;
- no uncontrolled card wall or auto-height masonry remains;
- no raw developer `Details` copy is visible in product surfaces;
- empty state is compact and attached to the primary surface;
- mobile stacks primary task before secondary/rail content;
- color remains low-saturation and finance-appropriate;
- route behavior, API semantics, auth, provider, scanner, portfolio, options,
  backtest, and report semantics are unchanged unless explicitly scoped.
