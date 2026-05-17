<!--
WolfyStock Reflect-Linear UI replacement document.
Source of truth image: docs/design/reference/wolfystock-reflect-linear-home-mockup.png
This document intentionally supersedes older deep-space / terminal / bento / generic Linear UI wording.
-->

# WolfyStock Reflect-Linear Visual Specification

Status: canonical visual source of truth for WolfyStock frontend UI/UX.  
Reference image: `docs/design/reference/wolfystock-reflect-linear-home-mockup.png`.

## 1. Design thesis

WolfyStock is a professional financial research OS. Its interface must feel calm, precise, low-key, premium, and data-centric. The visual language combines:

- **Reflect-like atmosphere**: dark canvas, muted violet glow, soft blur, subtle glass surfaces, ultra-thin borders, micro-noise, and refined depth.
- **Linear-like discipline**: structure first, strong alignment, restrained color, clear hierarchy, minimal chrome, and predictable product ergonomics.
- **Financial research density**: charts, signal levels, catalysts, rails, and rows are compact, legible, and decision-oriented.

The goal is not a trading-game dashboard, crypto casino, OLED terminal cosplay, or generic SaaS landing page. It is a serious research cockpit.

## 2. Mandatory visual qualities

### 2.1 Mood

Use these descriptors as the target taste:

```text
minimal / low-key / calm / cold / rational / premium / institutional / precise / luminous but restrained
```

Avoid:

```text
cheap neon / high-saturation purple / flashy crypto exchange / dribbble card wall / marketing hero page / noisy dashboard kits
```

### 2.2 Color system

Base colors should sit in a dark charcoal-to-midnight-navy ladder, never flat pure black as the only canvas.

Recommended intent tokens:

```text
Root canvas:       near-black navy, very low chroma
Shell canvas:      dark charcoal-navy
Console surface:   translucent midnight panel
Panel surface:     slightly lifted dark glass
Inset surface:     deeper chart/table well
Border:            ultra-thin cool gray-violet line
Primary accent:    muted violet, low saturation
Secondary accent:  cool blue-violet, restrained
Market green/red:  reserved for financial semantics only
Warning amber:     rare, only for risk/availability states
```

Color behavior:

- Purple is an atmospheric and interaction accent, not decoration sprayed everywhere.
- Green/red must remain market-semantic: gain/loss, bullish/bearish, valid/invalid risk states.
- Avoid saturated magenta, bright cyan, and large glowing blocks.
- Active states use thin underline, tiny pill fill, or soft focus glow, not heavy buttons.

### 2.3 Lighting and texture

Allowed:

- Soft violet/indigo bloom behind major console areas.
- Subtle gradient wash across the top or chart console.
- Extremely faint noise/grain overlay to prevent flatness.
- Light glass effect via transparency, blur, and inner shadow.
- Hairline borders and soft shadow only to separate regions.

Forbidden:

- Loud neon rings, giant plasma glows, saturated gradients across every card.
- Overpowering glassmorphism that reduces readability.
- Decorative 3D objects unrelated to the financial task.

## 3. Typography

Typography must be sober and precise.

- Preferred family: Inter / SF Pro / system sans-serif.
- Financial numbers should use tabular numerals where possible.
- Headings should be clear but not oversized.
- Labels are small, muted, and high-information.
- Avoid filler paragraphs. Copy must be concise and product-relevant.

Suggested scale intent:

```text
Nav / utility:      12-13px
Labels:             11-12px, muted
Body / rows:         13-14px
Metric values:       20-36px depending on importance
Page title:          22-30px
Hero stance value:   32-42px only when it anchors the surface
```

## 4. Layout principle

WolfyStock must use fixed layout regions before content is placed. Cards and panels are allowed, but only as controlled surfaces inside named regions.

Core rule:

```text
Cards/panels are allowed only inside predefined fixed regions with explicit sizing, overflow, and hierarchy. Do not create uncontrolled card sprawl, auto-height masonry, or variable-height panel stacks. If content exceeds its region, use internal scroll, collapsed disclosure, drawer, popover, or floating detail panel.
```

## 5. Canonical home layout

The home route is the canonical reference route.

Required zones:

1. **TopNavigation**
   - Slim brand/nav/utility row.
   - Active route uses thin violet underline or small pill.
   - Admin/control entry remains discoverable for authorized users.

2. **CommandBar**
   - Full-width query/search command bar below nav.
   - Soft border and restrained focus glow.
   - Analyze action at the right.

3. **ResearchConsole**
   - One dominant coherent console surface, not multiple unrelated cards.
   - Must contain the main stock analysis and right rail.

4. **PrimaryWorkRegion**
   - Stock identity, stance, score, confidence, core thesis, key levels, and chart.
   - Chart must be visually dominant.

5. **ContextRail**
   - Fixed width on desktop.
   - Contains research framework, data quality, compact metrics, and concise risk/level rows.
   - No free-floating cards.

6. **SecondaryDeck**
   - Attached catalyst/event row or compact table.
   - Must feel connected to the main console.
   - Not a detached card wall.

## 6. Surface hierarchy

Use this surface ladder consistently:

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

Avoid:

```text
Panel > Card > NestedCard > Details > Form > MoreCards
```

Maximum default visible nesting depth: **2**.

## 7. Motion guidance

Motion should be scarce, soft, and functional.

Allowed:

- Focus glow on command/search fields.
- Smooth drawer/panel reveal around 120-180ms.
- Subtle hover lift through border/glow, not scale bounce.
- Loading shimmer only when it clarifies wait state.

Forbidden:

- Bouncy animations.
- Constant pulsing glow.
- Large animated hero effects in product surfaces.
- Motion that competes with data.

## 8. Financial UI details

Charts:

- Chart wells should be dark inset surfaces with subtle grid lines.
- MA/indicator legends should be compact chips or row labels.
- Axis labels are muted and aligned.
- Toolbars are small and do not dominate.

Tables / rows:

- Prefer dense rows over individual cards for repeatable entities.
- Row height should be consistent.
- Actions should group at row end or in bounded rail/drawer.

Signals:

- Use small semantic pills, not large colorful badges.
- Risk/quality/coverage states should be concise.

## 9. Route family names

Use the following names to guide route composition:

```text
Home:             ResearchConsole
Scanner:          RankingBoard
Watchlist:        WatchBoard
Chat:             ResearchWorkspace
Market Overview:  MarketMonitor
Liquidity:        LiquidityMonitor
Rotation Radar:   RotationMonitor
Portfolio:        RiskConsole / LedgerBoard
Options Lab:      ExperimentConsole
Backtest:         ResearchRunConsole
Admin/Ops:        OpsConsole
Settings:         PreferenceConsole
```

## 10. Design acceptance checklist

A route passes only if all are true:

- Uses fixed named regions.
- No uncontrolled card sprawl.
- No auto-height masonry.
- No developer-looking default `Details` labels in main surfaces.
- Long secondary content is collapsed, internally scrollable, or in drawer/floating panel.
- Chart/table/list has clear primary status.
- Right rail is fixed and bounded on desktop.
- Mobile stacks primary task first, then secondary/rail.
- Color remains low-saturation and finance-appropriate.
- Visual result feels premium and calm, not cheap dashboard-kit UI.
