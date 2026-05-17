<!--
WolfyStock Reflect-Linear UI replacement document.
Source of truth image: docs/design/reference/wolfystock-reflect-linear-home-mockup.png
This document intentionally supersedes older deep-space / terminal / bento / generic Linear UI wording.
-->

# WolfyStock Frontend Surface Usage

Status: route surface taxonomy for Reflect-Linear Research OS.

## 1. Purpose

This document tells frontend workers which surface each route should use. It prevents every page from inventing its own card layout.

## 2. Universal page scaffold

Every major app route should follow this skeleton where applicable:

```text
TopNavigation
CommandBar or HeaderStrip
RouteConsole
  PrimaryWorkRegion
  ContextRail or FloatingDetailPanel
  SecondaryDeck
```

Routes may omit zones only when the workflow clearly does not need them.

## 3. Surface primitives and intent

### AppCanvas

Full-page dark navy/charcoal background with subtle atmospheric gradient and optional micro-noise.

### ShellBar / TopNavigation

Slim persistent nav. It must not become an admin toolbar. Admin/control tools go into compact utility menu.

### CommandBar

Search, query, AI command, or scanner command entry. It should feel like a focused input system, not a large filter card.

### RouteConsole

One coherent route-level surface. Use this instead of page-level card walls.

### PrimaryWorkRegion

The dominant task: chart, ranking table, watch rows, conversation, portfolio ledger, options decision board, or backtest result.

### ContextRail

Fixed-width supporting information on desktop. Bounded and internally scrollable when needed. On mobile, collapses below primary content or into drawer.

### MetricStrip / KeyLevelStrip

Compact summary rows. Avoid standalone metric cards unless each has equal size and a clear grid contract.

### DataRows

Default for repeatable data. Prefer rows over card-per-item.

### SecondaryDeck

Attached secondary material: catalysts, events, diagnostics summary, or related details. It should be compact by default.

### FloatingDetailPanel / Drawer

Use for dense details, advanced filters, long diagnostics, source drilldowns, and secondary workflows.

## 4. Route mapping

| Route family | Surface name | Primary region | Secondary / rail |
|---|---|---|---|
| Home | ResearchConsole | stock thesis + chart | observation rail + catalysts |
| Scanner | RankingBoard | candidate rows/table | selected candidate rail + collapsed diagnostics |
| Watchlist | WatchBoard | watch rows/list | compact filters + bounded detail |
| Chat | ResearchWorkspace | conversation + composer | evidence/context rail |
| Market Overview | MarketMonitor | market state + comparative boards | freshness/source rail |
| Liquidity | LiquidityMonitor | liquidity score + signal table | source/risk rail |
| Rotation Radar | RotationMonitor | ranked themes/sectors | selected theme detail rail |
| Portfolio | RiskConsole / LedgerBoard | holdings ledger | risk/activity rail |
| Options Lab | ExperimentConsole | scenario/strategy decision board | risk boundary rail |
| Backtest | ResearchRunConsole | result/compare workspace | parameters/details drawer |
| Admin/Ops | OpsConsole | operations table/queue | status/actions rail |
| Settings | PreferenceConsole | settings rows | help/details rail |

## 5. Containment rules

- Filters: `CompactFilterBar`; advanced filters collapsed.
- Diagnostics: collapsed by default unless the page is explicitly an Ops route.
- Details: never use raw `Details` as visible product copy.
- Tables: fixed row rhythm; actions grouped.
- Rails: fixed desktop width; bounded height; internal scroll for overflow.
- Cards: same-size cards only inside an explicit grid track.
- Empty states: compact and attached to the board, not large standalone slabs.

## 6. Screenshot acceptance

A screenshot should reveal the route’s primary task within the first viewport. If the first viewport is mostly filters, diagnostics, empty panels, or card stacks, the route fails.
