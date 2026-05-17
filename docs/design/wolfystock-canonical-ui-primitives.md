<!--
WolfyStock Reflect-Linear UI replacement document.
Source of truth image: docs/design/reference/wolfystock-reflect-linear-home-mockup.png
This document intentionally supersedes older deep-space / terminal / bento / generic Linear UI wording.
-->

# WolfyStock Canonical UI Primitives

Status: Reflect-Linear aligned primitive governance.

## 1. Purpose

This document defines the UI primitive ownership model. It is not an alternate design system. It defers to:

```text
docs/design/reference/wolfystock-reflect-linear-home-mockup.png
docs/design/WOLFYSTOCK_REFLECT_LINEAR_VISUAL_SPEC.md
docs/codex/WOLFYSTOCK_LINEAR_OS_DESIGN_LANGUAGE.md
docs/codex/WOLFYSTOCK_FRONTEND_SURFACE_USAGE.md
docs/codex/WOLFYSTOCK_FRONTEND_ROUTE_TEMPLATES.md
```

## 2. Primitive categories

### Layout primitives

- `FixedRegionGrid`
- `PrimaryWorkRegion`
- `ContextRail` / `RailPanel`
- `SecondaryDeck`
- `ScrollPanel`
- `FloatingDetailPanel`
- `Drawer`

These own geometry, overflow, and responsive stacking.

### Surface primitives

- `ResearchConsole`
- `RouteConsole`
- `GlassPanel`
- `ChartWell`
- `InsetSurface`

These own surface tone, borders, subtle glass, and glow levels.

### Data primitives

- `MetricStrip`
- `KeyLevelStrip`
- `DataRows`
- `EventRows`
- `SignalRows`
- `CompactTable`

These prevent card-per-item repetition.

### Control primitives

- `CommandBar`
- `CompactFilterBar`
- `SegmentedControl`
- `IconAction`
- `UtilityMenu`

These prevent full-width filter slabs and toolbar sprawl.

## 3. What primitives must prevent

Primitives should make bad layouts harder:

- No default auto-height card wall.
- No unbounded rails.
- No visible raw developer disclosures.
- No large empty states detached from primary board.
- No repeated local chip styles for the same status concept.

## 4. Surface token expectations

Primitives should consume shared tokens for:

- background ladder
- panel ladder
- border ladder
- focus ring
- violet glow intensity
- market semantic colors
- typography scale
- spacing density

Avoid route-local one-off values unless there is a clear exception.

## 5. Escape hatch rule

Every primitive may expose `className`, but page code must not use that to defeat the layout contract.

Allowed escape hatch examples:

- route-specific grid column ratio
- height cap for a specific rail
- min-height for chart well

Forbidden escape hatch examples:

- arbitrary card wall spacing
- nested panels inside panels for every content block
- hardcoded saturated colors outside tokens

## 6. Testing expectations

Primitive tests should verify:

- named regions render.
- rail is structurally bounded.
- scroll panels wrap overflow content.
- compact filter bars support primary and advanced controls.
- floating/drawer panels are available for secondary detail.

Route tests should verify:

- primary work region exists.
- context rail is not detached.
- secondary content is collapsed/contained by default.
- no bento/card-grid architecture persists for migrated routes.
