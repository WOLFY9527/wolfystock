# WolfyStock Terminal Primitives Usage

This file name is kept for compatibility with older prompts and existing `Terminal*` exports.

`Terminal*` primitives are legacy-compatible component names only. They must render WolfyStock Linear OS material. They are not the preferred architecture for new user-facing work.

New user-facing work should prefer:

```text
apps/dsa-web/src/components/linear/
```

## Current Rule

Existing pages may keep importing these names during migration:

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
- dense workbench helpers

These names must map to:

- charcoal surface ladder;
- thin separators;
- compact row density;
- restrained blue active/focus state;
- market green/red only for market semantics;
- rows/tables/strips/rails before cards.

## What This File No Longer Allows

Do not use this file to justify:

- treating `TerminalPageShell` or `TerminalPanel` as the future route architecture;
- local page material systems;
- nested panel hierarchies as default layout;
- decorative material effects as ordinary hierarchy;
- widened old cards as a new design system;
- user-facing admin/backend density on product routes.

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
