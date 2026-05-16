# WolfyStock Terminal Primitives Usage

This file name is kept for compatibility with older prompts and existing `Terminal*` exports.

The old terminal, ghost-glass, cyber, OLED, and card-first guidance is retired. `Terminal*` primitives are legacy-compatible names only. They must render WolfyStock Linear OS material.

New user-facing work should prefer:

```text
apps/dsa-web/src/components/linear/
```

## Current Rule

Existing pages may keep importing `TerminalPageShell`, `TerminalPanel`, `TerminalNestedBlock`, `TerminalButton`, `TerminalChip`, `TerminalDisclosure`, and dense workbench helpers.

Those names must now map to:

- charcoal surface ladder;
- thin separators;
- compact row density;
- restrained blue active/focus state;
- market green/red only for market semantics;
- no glow, no glass, no OLED, no terminal cosplay.

## Retired Defaults

Do not use these as normal primitive material:

- `backdrop-blur-*` on scrolling panels;
- `bg-black`, `bg-black/20`, or pure black nested block defaults;
- gradient CTA as the default primary action;
- outer glow, neon shadow, or spotlight border;
- `TerminalPageShell` or `TerminalPanel` as the preferred future architecture;
- many nested panels to simulate hierarchy.

## Compatibility Exports

Expected legacy exports still exist:

- `TerminalPageShell`
- `TerminalGrid`
- `TerminalPanel`
- `TerminalNestedBlock`
- `TerminalSectionHeader`
- `TerminalPageHeading`
- `TerminalMetric`
- `TerminalButton`
- `TerminalChip`
- `TerminalEmptyState`
- `TerminalNotice`
- `TerminalDenseList`
- `TerminalDenseTable`
- `TerminalDisclosure`

They should be treated as adapters while route migrations move toward `components/linear`.

## Future-Facing Linear Primitives

Use these for new Linear OS work:

- `WolfyShellSurface`
- `WolfyCommandBar`
- `ResearchConsoleShell`
- `ConsoleBoard`
- `ConsoleContextRail`
- `ConsoleStatusStrip`
- `ConsoleDisclosure`
- `KeyLevelStrip`
- `CatalystRows`
- `DataWorkbenchFrame`
- `DenseRows`

## Page-File Rules

Page files should own:

- route-specific hierarchy;
- grid columns and responsive ordering;
- data mapping and product copy;
- behavior and state orchestration.

Shared primitives should own:

- surface material;
- radius and border;
- row density;
- button, chip, notice, empty-state, and disclosure styling;
- command bar and context rail rhythm.

Avoid page-local material classes for panels, chips, buttons, notices, empty states, and table frames unless the task explicitly requires a new primitive.

## Migration Note

Add comments where helpful:

```tsx
// Legacy-compatible name; new user-facing work should prefer components/linear.
```

Do not rename existing exports in a foundation task. Compatibility is part of the contract.
