# WolfyStock Guided Disclosure Primitives

Date: 2026-05-09
Branch: `main`
Scope: shared frontend primitives only. No production page, backend, provider,
scanner, portfolio, Options, backtest, launch acceptance, Shell, Sidebar, or
global CSS files were changed.

## Purpose

Launch UX audits found the same density problem across Scanner, Portfolio,
Options, Backtest, and Admin/Ops surfaces: pages often show configuration,
diagnostics, raw provider/cache terms, evidence, and actions before the user
sees the primary story. These primitives provide a shared pattern for showing
summary first and details second without deleting useful evidence.

## Components

### `SectionIntro`

Use at the top of a route section or major card group.

- Shows a purpose label.
- Shows one plain-language summary line.
- Can include the next safe step.
- Can include a small status badge.

Best fit:

- Scanner: candidate shortlist purpose and scan readiness.
- Portfolio: ledger/read-only portfolio state before manual record details.
- Options: safety/readiness framing above chain details.
- Backtest: result story before evidence controls.
- Admin/Ops: operator readiness before provider/cache internals.

### `InsightStack`

Use when a page has multiple findings but only a few should lead.

- Accepts prioritized insights.
- Shows only the first four items by default.
- Supports `critical`, `warning`, `info`, and `success` severities.
- Keeps optional detail attached to each insight without creating a new card pile.

Best fit:

- Scanner: top candidate blockers and observations.
- Portfolio: concentration, FX, stale sync, and missing ledger evidence.
- Options: strategy safety checks and missing assumptions.
- Backtest: top drivers of result confidence.
- Admin/Ops: blocked capability, degraded data source, or safe-to-proceed notes.

### `GuidedDisclosure`

Use for details that should remain available but not dominate the default view.

- Uses native `details` and `summary`.
- Defaults collapsed.
- Provides beginner explanation and professional detail areas.
- Avoids custom scroll containers and native-looking controls.
- Keyboard users can focus and toggle the summary through native browser behavior.

Best fit:

- Scanner diagnostics, provider detail, history, and raw expansion evidence.
- Portfolio broker sync/import evidence and manual record caveats.
- Options chain assumptions and provider/debug detail.
- Backtest execution assumptions, trace, ledger, and export evidence.
- Admin/Ops raw payload, schema, route, TTL, bucket, and maintenance context.

### `DensityRail`

Use as a compact secondary context rail next to a primary narrative.

- Should carry small facts, filters, freshness states, or guardrails.
- Should not contain primary actions.
- Should stay visually quieter than the main content.

Best fit:

- Scanner market/profile context.
- Portfolio currency, sync, and account context.
- Options expiration/data readiness context.
- Backtest sample window and benchmark context.
- Admin/Ops role/scope/offline status context.

### `MetricNarrativeCard`

Use when a number needs plain-language interpretation.

- Shows metric value.
- Explains what the metric means.
- Includes uncertainty or freshness.
- Can link a glossary term label for future help affordances.

Best fit:

- Scanner candidate score, confidence, and liquidity signals.
- Portfolio exposure, P&L, FX translation, and sync freshness.
- Options IV/risk/strategy readiness metrics.
- Backtest win rate, drawdown, sample size, and confidence.
- Admin/Ops cost, quota, circuit, and evidence health metrics.

## Usage Rules

- Lead with one `SectionIntro`, then use `InsightStack` or
  `MetricNarrativeCard` for the primary story.
- Use `GuidedDisclosure` for evidence, diagnostics, raw fields, provider/cache
  language, schema, trace, and maintenance context.
- Use `DensityRail` only for secondary context. Do not place primary CTAs in it.
- Do not nest disclosures inside disclosures unless a page has a documented
  operator workflow that requires it.
- Do not hide risk or safety state behind a disclosure. Safety status must be
  visible before details.
- Do not turn every sentence into a tooltip or glossary hook. Add glossary hooks
  only for durable product terms that recur across pages.
- Do not use disclosures as a substitute for hierarchy. If everything is
  collapsed, the page still needs a clearer primary story.
- Keep developer/debug labels collapsed by default and map launch-facing copy to
  product language such as `数据不足`, `部分可用`, `等待快照`, or `只读证据`.

## Design Notes

- Visual language follows deep-space ghost glass: transparent white surfaces,
  black inner blocks, subtle borders, restrained cyan/emerald/amber/rose tones.
- Components avoid solid gray backgrounds and native-looking controls.
- The disclosure primitive uses native semantics for keyboard and screen-reader
  behavior rather than a custom clickable `div`.
- Components are mobile-friendly by default: rail items wrap into a two-column
  mobile grid and disclosure detail columns stack before splitting on desktop.
