# WolfyStock Consumer Data Quality UX

Status: current consumer-facing data-quality UX contract.

This document defines how WolfyStock consumer-facing product pages should
present data quality, confidence, freshness, and temporary unavailability
without exposing backend diagnostic vocabulary or maintainer-facing detail.

## Product Scope

WolfyStock is ToC by default.

Consumer-facing pages must never expose backend diagnostic vocabulary by
default. They should convert data-quality problems into graceful product states
that preserve user trust without making the product look broken, unstable, or
developer-operated.

This document applies to consumer-facing product routes. Admin, backstage, and
maintenance routes must follow
`docs/frontend/WOLFYSTOCK_ADMIN_MAINTENANCE_OS.md` instead.

## Consumer UX Principle

Consumer pages should preserve trust, show honest limits, and avoid diagnostic
walls.

When consumer-facing data quality is degraded, incomplete, or unavailable, the
UI should convert the issue into:

- soft product status
- limited confidence indicator
- last updated time
- optional one-line user-safe explanation
- never a diagnostic wall

The consumer UI should answer:

1. Can the user still use this feature?
2. If not fully, what product state applies now?
3. How confident is the current output?
4. When was the current data last updated?

## Consumer-Safe Status Vocabulary

Consumer-facing routes should use only bounded product status words:

- `AVAILABLE`
- `UPDATING`
- `DELAYED`
- `PARTIAL`
- `INSUFFICIENT`
- `PAUSED`
- `UNAVAILABLE`

These are product states, not backend contract dumps.

## Forbidden Consumer Vocabulary

The following vocabulary must not appear by default on consumer-facing pages:

- `sourceAuthorityAllowed`
- `scoreContributionAllowed`
- `observationOnly`
- `reasonCode` / `reasonFamilies`
- provider trace
- provider class names
- `fallback_static`
- `synthetic_fixture`
- `official_public`
- `authorized_licensed_feed`
- `public_proxy` / `unofficial_proxy`
- `Polygon` / `Tushare` / API key / internal provider failure details unless
  inside admin-only routes
- raw JSON
- raw diagnostics
- backend snake_case field names
- remediation instructions intended for maintainers

Consumer pages must also avoid raw provider failure wording, entitlement
details, internal source-confidence labels, and implementation-oriented field
explanations by default.

## Consumer Translation Rules

Consumer pages should translate data-quality problems into product language.

Preferred conversions:

- blocked scoring -> `评分已暂停` or `数据不足`
- stale but usable -> `已使用最近一次可用数据`
- temporary refresh window -> `数据更新中，稍后将自动刷新`
- incomplete but viewable -> `当前信号置信度较低，仅供观察`
- unavailable module -> `本模块暂不可用，请稍后重试`
- partial dependency loss -> `部分数据暂不可用`

Consumer-safe example copy:

- `部分数据暂不可用，当前评分已暂停。`
- `数据更新中，稍后将自动刷新。`
- `当前信号置信度较低，仅供观察。`
- `本模块暂不可用，请稍后重试。`
- `已使用最近一次可用数据。`

Copy rules:

- Use product language, not backend field names.
- Prefer one short sentence over multi-line diagnostic explanation.
- Preserve honesty about confidence and freshness.
- Do not make the page sound like an internal incident console.

## UI Contract

Consumer data-quality UI should use:

- one soft product status at page or module level;
- a bounded confidence indicator when confidence is capped;
- a visible last updated time where freshness matters;
- an optional one-line user-safe explanation;
- collapsed or absent technical details by default.

Consumer routes should never default to a developer-style disclosure stack of
provider names, reason trees, JSON, or maintainer action items.

## Route Guidance

### Home

- No backend diagnostics.
- Show only product-level readiness and feature access state.
- If a feature is degraded, describe the product impact, not the provider
  incident behind it.

### Market Overview

- Show market conclusions, confidence, and limited data status.
- Hide provider, source, and freshness internals beyond user-safe timestamps
  and bounded status.
- The user should see what the market view currently supports, not how the
  backend assembled it.

### Liquidity Monitor

- Show whether the liquidity read is available, partial, paused, or unavailable.
- Do not expose provider details, score-blocking field names, or fallback
  diagnostics.
- If liquidity confidence is capped, present it as a product limitation.

### Rotation Radar

- Show whether the rotation signal is available, delayed, partial, or
  insufficient.
- Do not expose taxonomy/provider debug language.
- Explain low confidence as a user-safe signal limitation, not a backend
  pipeline explanation.

### Scanner

- Show candidate confidence and freshness.
- Do not show reason codes by default.
- Candidate unavailability or paused scoring should appear as product-state
  language rather than diagnostic exclusion language.

### Watchlist

- Show item-level freshness and confidence.
- Do not expose scanner internals, source-confidence fields, or provider
  explanation trees by default.
- If one item is delayed, keep the message local and user-readable.

### Portfolio

- Show stale or delayed pricing in user language.
- Do not expose provider diagnostics, entitlement state, or internal fallback
  detail.
- The user should understand whether pricing is current enough for observation.

### Backtest

- Show run reliability and reproducibility status in product language.
- Keep raw support details behind an advanced or admin-only path.
- Do not expose trace JSON, helper metadata, or storage contract detail in the
  normal consumer surface.

## Separation Rule

Consumer-facing product pages must not use
`WOLFYSTOCK_ADMIN_MAINTENANCE_OS.md` as permission to show backend diagnostic
detail.

If a route is consumer-facing:

- data-quality issues become graceful product states;
- confidence limits become bounded user-safe explanations;
- maintainer repair instructions move to admin-only surfaces;
- technical diagnostics stay absent by default or behind an explicit admin-only
  path.

## Acceptance Checklist

- Does the route serve consumers by default?
- Are data-quality issues expressed as product state rather than raw
  diagnostics?
- Are provider names, reason codes, backend fields, and raw diagnostics absent
  by default?
- Is confidence shown in user-safe language?
- Is freshness expressed through last updated time or bounded delay status?
- Does the page avoid maintainer remediation instructions?
- Does the page preserve trust without pretending degraded data is fully live?

If any answer is no, the route does not meet the consumer data-quality UX
contract.
