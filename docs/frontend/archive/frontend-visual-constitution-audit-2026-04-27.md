# WolfyStock Frontend Visual Constitution Audit

Date: 2026-04-27

Scope:
- Repo: `apps/dsa-web/src`
- This pass audits the current shell, shared routes, and representative page containers against the WolfyStock design constitution.
- Implementation scope for this pass is intentionally limited to shared `Layout/Nav` so existing page business logic and the user's in-flight Home edits remain untouched.

## Constitution Summary

1. Layout and container tokens
   - Shared shell must be edge-to-edge.
   - Header, sub-nav, and route frame must not sit inside centered `max-width` cages.
   - Shared safe gutters should come from `px-6 md:px-8 xl:px-12` equivalent tokens, not ad hoc page wrappers.
2. Material and dark-theme tokens
   - Base canvas stays near `#030303` or `#050505`.
   - Shared cards, drawers, and nav controls should use restrained glass surfaces instead of opaque gray slabs or neon-heavy chrome.
3. Typography and density tokens
   - Large display sizes must stay rare.
   - Dense workspace copy should prefer compact uppercase labels and tight body leading.
4. Semantic color strictness
   - Green is reserved for gains, positive PnL, and growth semantics only.
   - System focus, selection, and CTA states should converge on neutral white or cool indigo/blue.

## Audit Findings

### P0 Shared Shell Violations

- `apps/dsa-web/src/index.css`
  - Shared shell overrides still pin `.shell-masthead__inner` and `.shell-content-frame` to `max-width: var(--layout-page-max)` and `margin: 0 auto`, which directly violates the edge-to-edge rule.
  - Current shell styling still carries SpaceX-era neon gradient brand treatments and underline-style nav activation instead of restrained glass tokens.
- `apps/dsa-web/src/components/layout/Shell.tsx`
  - The JSX shell structure was close, but it did not explicitly enforce `w-full min-w-0` on the route frame and main lane.
- `apps/dsa-web/src/components/layout/SidebarNav.tsx`
  - Shared nav controls used the legacy theme classes only; there was no explicit primary CTA variant and the visual language still depended on old theme overrides.
- `apps/dsa-web/src/components/layout/PreviewShell.tsx`
  - Preview routes share the same masthead and frame problem, so they must align with the same shell tokens.

### P1 Route Container Violations Still Pending

- `apps/dsa-web/src/pages/ChatPage.tsx`
  - Still contains `mx-auto` with `max-w-4xl` and `max-w-5xl` message-stage wrappers.
- `apps/dsa-web/src/pages/PortfolioPage.tsx`
  - Still uses `workspace-width-wide mx-auto ... max-w-[1920px]`.
- `apps/dsa-web/src/pages/UserScannerPage.tsx`
  - Still uses `mx-auto` with `max-w-[1920px]`.
- `apps/dsa-web/src/pages/SettingsPage.tsx`
  - Still uses `mx-auto ... max-w-[1600px]`.
- `apps/dsa-web/src/pages/AdminLogsPage.tsx`
  - Still uses `mx-auto ... max-w-[1600px]`.
- `apps/dsa-web/src/pages/PersonalSettingsPage.tsx`
  - Still uses centered `mx-auto max-w-4xl`.

These are phase-2 targets after the shared shell is stable.

### P2 Typography and Semantic Color Violations Still Pending

- Oversized headings remain in `HomeBentoDashboardPage.tsx`, `GuestHomePage.tsx`, `ChatPage.tsx`, `AdminLogsPage.tsx`, and settings components.
- Non-profit green still appears in UI controls or decorative states in:
  - `GuestHomePage.tsx`
  - `UserScannerPage.tsx`
  - `PersonalSettingsPage.tsx`
  - `SettingsPage.tsx`

These need page-level refactors after route containers are normalized.

## Phase Plan

### Phase 1: Shared Layout/Nav Token Alignment

Status: implemented in this pass

- Remove shared shell max-width constraints from masthead and route frame.
- Standardize shell gutters, dark canvas, glass nav surfaces, drawer surfaces, and route-frame width handling.
- Introduce a neutral primary CTA treatment for sign-in while keeping danger actions red-only.
- Keep the runtime theme key as `spacex` for compatibility, but make the visual output follow WolfyStock tokens.

### Phase 2: Route Container Normalization

Targets:
- `ChatPage.tsx`
- `PortfolioPage.tsx`
- `UserScannerPage.tsx`
- `SettingsPage.tsx`
- `AdminLogsPage.tsx`
- `PersonalSettingsPage.tsx`

Goals:
- Remove stray `mx-auto`, `container`, and page-level `max-w-*` wrappers from workspace routes.
- Keep article-like reading zones narrow only where reading comfort is the actual product goal.

### Phase 3: Surface, Typography, and Semantic Color Alignment

Targets:
- Replace opaque dark slabs with consistent glass material.
- Introduce dense label/value tokens where dashboards still use oversized typography.
- Remove decorative green from general UI controls and reserve it for profit/growth semantics only.

### Phase 4: Browser-First Acceptance

Required route checks after each phase:
- `/`
- `/scanner`
- `/chat`
- `/portfolio`
- `/backtest`
- `/settings`
- `/settings/system`
- `/admin/logs`
- `__preview` routes that share the shell

Success criteria:
- No centered outer shell.
- Header remains full-width at desktop breakpoints.
- Route frame expands naturally to the viewport edges with only safe gutters.
- Shared nav, drawer, and dialog surfaces read as one system.
