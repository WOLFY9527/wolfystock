<!--
WolfyStock Reflect-Linear UI replacement document.
Source of truth image: docs/design/reference/wolfystock-reflect-linear-home-mockup.png
This document intentionally supersedes older deep-space / terminal / bento / generic Linear UI wording.
-->

# Codex Frontend Design Constitution

Status: frontend guardrail for all Codex UI tasks.

## 1. Source of truth

The visual source of truth is:

```text
docs/design/reference/wolfystock-reflect-linear-home-mockup.png
```

Codex must treat this as stronger than older screenshots, old mockups, and generic descriptions.

## 2. Required taste standard

The frontend must feel:

```text
calm / premium / low-saturation / dark / structured / financial / precise / professional
```

It must not feel:

```text
cheap / flashy / noisy / crypto-casino / generic dashboard kit / terminal cosplay / dribbble card wall
```

## 3. Non-negotiable card containment rule

Cards/panels are allowed only inside predefined fixed regions with explicit sizing, overflow, and hierarchy. Do not create uncontrolled card sprawl, auto-height masonry, or variable-height panel stacks. If content exceeds its region, use internal scroll, collapsed disclosure, drawer, popover, or floating detail panel.

## 4. Route task procedure

Every frontend route task must do this before editing:

1. Identify route family.
2. Declare named zones.
3. Identify primary work region.
4. Identify rail/secondary content.
5. Decide overflow strategy.
6. Update tests to protect the layout contract.
7. Capture fresh browser evidence.

## 5. Forbidden default outcomes

- First viewport dominated by filters.
- Diagnostics expanded by default.
- Raw `Details` visible in main product surface.
- Empty state as a giant standalone card.
- Right rail as a pile of tiny cards/chips.
- Repeated route-local card styles.
- Saturated purple/blue glow used as decoration rather than hierarchy.

## 6. Screenshot gate

Do not claim success from tests alone. A route fails if fresh screenshots still show uncontrolled layout, even when all tests pass.

Browser checks should include at least:

- 1440x1000
- 1920x1080 when route is desktop-heavy
- 390x844 for mobile behavior

## 7. Protected behavior

UI refactors must preserve route behavior and API semantics. Do not change backend, provider, auth, account, scoring, ranking, strategy, options, backtest, or portfolio semantics unless the task explicitly allows it.
