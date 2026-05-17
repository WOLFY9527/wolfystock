<!--
WolfyStock Reflect-Linear UI replacement document.
Source of truth image: docs/design/reference/wolfystock-reflect-linear-home-mockup.png
This document intentionally supersedes older deep-space / terminal / bento / generic Linear UI wording.
-->

# WolfyStock Frontend Route Templates

Status: implementation templates for Reflect-Linear Research OS.

## 1. Common template

```tsx
<RouteConsole>
  <HeaderStrip />
  <CommandBar />
  <FixedRegionGrid>
    <PrimaryWorkRegion>
      {/* chart/table/conversation/decision workspace */}
    </PrimaryWorkRegion>
    <ContextRail>
      {/* compact supporting rows */}
    </ContextRail>
  </FixedRegionGrid>
  <SecondaryDeck>
    {/* compact rows/timeline/diagnostic summary */}
  </SecondaryDeck>
</RouteConsole>
```

The exact components may differ, but the zone contract must be visible in DOM/tests.

## 2. Home / ResearchConsole

Purpose: single-symbol research cockpit.

Required:

- Command bar above console.
- Company identity and current research stance.
- Score, confidence, and data-quality state.
- Key level strip.
- Large chart as primary visual anchor.
- Fixed context rail with observation framework and quality summary.
- Bottom catalyst/event deck.

Forbidden:

- Detached chart card + detached rail + detached event card pile.
- Large paragraph blocks in rail.
- Random metrics cards outside region contract.

## 3. Scanner / RankingBoard

Purpose: candidate ranking and selection workflow.

Required:

- Compact filter bar.
- Ranking rows/table as primary work region.
- Selected candidate detail in bounded rail/floating panel.
- Diagnostics/backtest/comparison collapsed by default.

Forbidden:

- First viewport dominated by filters.
- Always-expanded diagnostics.
- Visible raw `Details` label.

## 4. Watchlist / WatchBoard

Purpose: monitored symbols and actions.

Required:

- Compact filters.
- Watch rows/list as primary region.
- Compact empty state attached to board.
- Batch actions in secondary action row.
- Advanced filters collapsed.

Forbidden:

- Filter slab owning first viewport.
- Empty card detached from board.
- Batch controls as large full-width panel.

## 5. Chat / ResearchWorkspace

Purpose: AI research conversation with evidence.

Required:

- Bounded conversation `ScrollPanel`.
- Anchored composer.
- Evidence/context rail collapsed or bounded.
- Suggested prompts as compact chips/rows.

Forbidden:

- Giant blank conversation slab.
- Right rail taller/noisier than primary workspace.
- Always-open evidence blocks.

## 6. Market Overview / MarketMonitor

Purpose: broad market state.

Required:

- Top market state strip.
- Dominant market monitor surface.
- Comparative boards as equal-height regions.
- Freshness/source detail collapsed or in rail.

Forbidden:

- Old dashboard card mosaic.
- Many uneven cards of market indicators.

## 7. Portfolio / RiskConsole

Purpose: holdings, exposure, and risk.

Required:

- Ledger/table as primary region.
- Risk summary rail.
- Activity/reconciliation collapsed into secondary deck.

Forbidden:

- Large empty account cards.
- Portfolio metrics as random card grid.

## 8. Options Lab / ExperimentConsole

Purpose: scenario and strategy evaluation.

Required:

- Compact scenario command strip.
- Strategy rows/decision matrix.
- Risk boundary rail.
- Chain/payoff details contained in scroll/drawer.

Forbidden:

- Stacked warning boxes and oversized forms.

## 9. Backtest / ResearchRunConsole

Purpose: run, compare, and interpret backtests.

Required:

- Result/compare workspace as primary region.
- Parameters and historical details in drawer/rail.
- Metrics in controlled strips.

Forbidden:

- Card-based form wall.

## 10. Admin/Ops / OpsConsole

Purpose: operations and maintenance.

Allowed to be denser and more table-driven, but still uses controlled regions.

Required:

- Operation queue/table as primary region.
- Status rail.
- Dangerous actions clearly grouped and low-noise.

Forbidden:

- Admin nav clutter in product nav.
- Diagnostic card sprawl.
