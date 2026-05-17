<!--
WolfyStock Reflect-Linear UI replacement document.
Source of truth image: docs/design/reference/wolfystock-reflect-linear-home-mockup.png
This document intentionally supersedes older deep-space / terminal / bento / generic Linear UI wording.
-->

# WolfyStock Reflect-Linear Design Language

Status: canonical frontend design language.
Visual source: `docs/design/reference/wolfystock-reflect-linear-home-mockup.png`.

## 1. Name

The WolfyStock frontend design language is:

```text
Reflect-Linear Research OS
```

It replaces older wording such as generic Linear OS, deep-space terminal, ghost UI, OLED terminal, bento dashboard, or card-first dashboard.

## 2. Essence

Reflect-Linear Research OS is built from three constraints:

1. **Reflect atmosphere**: dark, luminous, glass-light, finely bordered, softly glowing.
2. **Linear discipline**: structured, minimal, aligned, fast, and low-noise.
3. **Financial seriousness**: dense data, exact semantics, restrained emotion, and decision clarity.

## 3. Core visual rules

### Allowed

- Deep navy/charcoal canvas.
- Low-saturation violet focus/accent.
- Thin cool borders.
- Subtle glass panels.
- Soft violet/indigo glow as atmosphere.
- Fine noise texture.
- Dense rows/tables for repeatable data.
- Controlled panels/cards within fixed regions.

### Forbidden

- Cheap neon dashboard style.
- Bright purple saturation everywhere.
- Random card grids.
- Auto-height masonry layouts.
- Oversized empty cards.
- Decorative panels that do not serve task hierarchy.
- Visible raw/developer UI labels such as default `Details` in product surfaces.
- Page-local layout improvisation.

## 4. The card rule

Do not say “no cards.” Cards are not the problem.

Correct rule:

```text
Cards and panels are allowed only inside predefined layout regions with fixed sizing, explicit overflow behavior, and clear hierarchy.
```

Bad:

```text
A page is assembled by stacking cards until everything fits.
```

Good:

```text
A page declares a region contract first, then each surface occupies a known role: primary work, rail, strip, drawer, or secondary deck.
```

## 5. Region contract

Every route must declare which of these it uses:

- `HeaderStrip`
- `CommandBar`
- `PrimaryWorkRegion`
- `ContextRail`
- `MetricStrip`
- `KeyLevelStrip`
- `ChartWell`
- `DataRows`
- `SecondaryDeck`
- `FloatingDetailPanel`
- `Drawer`

No route should introduce arbitrary new card zones without justification.

## 6. Visual density

WolfyStock should feel data-rich but not crowded.

- Top-level panels should have generous but purposeful spacing.
- Dense content belongs in rows/tables, not paragraph blocks.
- Right rail content uses labeled rows and separators.
- Secondary diagnostics are collapsed by default.
- Long filters are compressed into `CompactFilterBar` with advanced options behind disclosure/drawer.

## 7. Home target

Home is the flagship reference:

```text
Slim nav
Full command bar
One dominant ResearchConsole
Left PrimaryWorkRegion
Fixed ContextRail
Attached SecondaryDeck
Muted violet glow and glass-light surfaces
```

Do not make Home a landing page or a card mosaic.

## 8. Implementation posture for Codex

When implementing frontend UI:

1. Read the visual source image first.
2. Identify the route family.
3. Declare fixed zones in the implementation and tests.
4. Place content into those zones.
5. Collapse or contain overflow.
6. Validate screenshots at desktop and mobile sizes.

A route is not considered migrated just because it imports `LinearPrimitives` or uses a renamed `ConsoleBoard`.
