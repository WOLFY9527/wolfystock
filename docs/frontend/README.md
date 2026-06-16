# WolfyStock Frontend Docs

Status: current frontend documentation entry point.

Use this lane before changing `apps/dsa-web/`, route UI, shared frontend
primitives, visual validation, frontend copy hierarchy, or CSS ownership. This
README is the canonical current frontend map; historical frontend audits are
archive provenance only.

## Current Authority

- [Frontend Visual System](./visual-system.md): Reflect-Linear design
  language, route surface taxonomy, layout/primitive rules, information
  hierarchy, and guided-help policy.
- [Frontend Validation Playbook](./validation-playbook.md): fresh browser
  evidence, route visual gates, UX density harness, CSS cleanup proof, and
  frontend final-report fields.
- `docs/design/reference/wolfystock-reflect-linear-home-mockup.png`: visual
  target image. It is not current implementation proof and must not be moved.

## What Was Consolidated

The frontend lane replaces these former active documents:

- `docs/codex/WOLFYSTOCK_LINEAR_OS_DESIGN_LANGUAGE.md`
- `docs/codex/CODEX_FRONTEND_DESIGN_CONSTITUTION.md`
- `docs/codex/WOLFYSTOCK_FRONTEND_SURFACE_USAGE.md`
- `docs/codex/WOLFYSTOCK_FRONTEND_ROUTE_TEMPLATES.md`
- `docs/codex/WOLFYSTOCK_TERMINAL_PRIMITIVES_USAGE.md`
- `docs/codex/WOLFYSTOCK_FRONTEND_VALIDATION_PLAYBOOK.md`
- `docs/codex/WOLFYSTOCK_CODEX_VISUAL_EVIDENCE_PROTOCOL.md`
- `docs/design/WOLFYSTOCK_REFLECT_LINEAR_VISUAL_SPEC.md`
- `docs/design/wolfystock-canonical-ui-primitives.md`
- `docs/audits/frontend-information-density-and-guidance-standard.md`
- `docs/audits/frontend-guided-information-system.md`
- `docs/audits/frontend-guided-disclosure-primitives.md`
- `docs/audits/frontend-domain-education-copy-pack.md`
- `docs/audits/frontend-ux-density-audit-harness.md`

Point-in-time frontend audit and CSS evidence moved to
`docs/frontend/archive/` or remains under `docs/audits/archive/frontend/`.

## Route Families

| Route family | Surface | Current start point |
| --- | --- | --- |
| Home | ResearchStart | [Visual System](./visual-system.md#route-surface-taxonomy) |
| Decision Cockpit | MarketStructureCockpit | `apps/dsa-web/src/pages/MarketDecisionCockpitPage.tsx` |
| Market Overview | MarketMonitor | [Market Overview domain](../market-overview/README.md) |
| Liquidity | LiquidityMonitor | [Liquidity domain](../liquidity/README.md) |
| Rotation Radar | RotationMonitor | [Rotation domain](../rotation/README.md) |
| Research Radar | ResearchQueue | `apps/dsa-web/src/pages/ResearchRadarPage.tsx` |
| Stock Structure | StructureDecisionWorkbench | `apps/dsa-web/src/pages/StockStructureDecisionEntryPage.tsx` |
| Scanner | ResearchContextBoard | [Scanner domain](../scanner/README.md) |
| Watchlist | WatchBoard | [Visual System](./visual-system.md#route-template-requirements) |
| Portfolio | RiskConsole / LedgerBoard | [Portfolio domain](../portfolio/README.md) |
| Options/Gamma Observation | ObservationConsole | [Options domain](../options/README.md) |
| Scenario Lab | ScenarioPlaceholder | `apps/dsa-web/src/pages/ScenarioLabPage.tsx` |
| Backtest | ResearchRunConsole | [Backtest domain](../backtest/README.md) |
| Admin/Ops | OpsConsole | [Admin/Ops domain](../admin-ops/README.md) |
| Settings | PreferenceConsole | [Visual System](./visual-system.md#route-surface-taxonomy) |

## Research Cockpit IA v1

The current consumer frontend is organized around a professional Market
Structure + Positioning Intelligence workflow:

- `/market/decision-cockpit` is the primary market entry and leads with market
  regime, research queue preview, confidence limits, and Options/Gamma
  observation boundaries.
- `/market-overview` remains the broader market map. `/market/liquidity-monitor`
  and `/market/rotation-radar` are deep market routes rather than top-level
  consumer navigation items.
- `/research/radar` is the core research queue for turning market-structure
  clues into reviewable single-name candidates.
- `/stocks/structure-decision` is the stock-structure entry route, while
  `/stocks/:stockCode/structure-decision` opens a specific structure workspace.
- `/scanner`, `/watchlist`, and `/portfolio` remain research-context entries.
- `/options-lab` is labeled as observation/validation context; Options/Gamma
  status must remain `observationOnly=true` and `decisionGrade=false` where
  surfaced.
- `/scenario-lab` is a static placeholder entry until a backend scenario API is
  available in the active branch.

Primary implementation anchors:

- Market Decision Cockpit:
  `apps/dsa-web/src/pages/MarketDecisionCockpitPage.tsx`
- Stock Structure detail:
  `apps/dsa-web/src/pages/StockStructureDecisionPage.tsx`
- Stock Structure entry:
  `apps/dsa-web/src/pages/StockStructureDecisionEntryPage.tsx`
- Research Radar:
  `apps/dsa-web/src/pages/ResearchRadarPage.tsx`
- Scenario Lab placeholder:
  `apps/dsa-web/src/pages/ScenarioLabPage.tsx`

These routes reuse the shared Shell plus consumer workspace primitives, keep
Admin/Ops separate, avoid broker/order/trade controls, avoid raw provider/debug
payload leakage, and keep observation-only / no-advice copy boundaries.

## Implementation Rules

- Preserve frontend behavior, route permissions, API contracts, provider
  semantics, scanner scoring, portfolio accounting, options safety, backtest
  calculations, report payloads, and auth behavior unless the task explicitly
  scopes those domains.
- New user-facing work should prefer `apps/dsa-web/src/components/linear/`.
- Existing `Terminal*` imports are compatibility adapter names only and must
  render Reflect-Linear material.
- Page files own route hierarchy, state, product copy, grid ratios, and data
  mapping. Shared primitives own reusable material, density, button/chip/
  notice/empty/disclosure styling, command bars, and rails.
- User routes lead with page intent, current state, the primary user question,
  safe next step, and evidence summary before details.
- Admin/Ops pages may show more diagnostics but still start with operator
  state, impact, recommended action, evidence, then details.

## Validation Rules

Use [Frontend Validation Playbook](./validation-playbook.md) for current
commands and browser-evidence expectations. A route is not visually accepted
from tests alone; fresh screenshots from current HEAD and a task-owned server
are required for UI claims.

Docs-only frontend taxonomy cleanup does not require browser verification by
itself, but must still run docs/governance checks requested by the task.

## Archive Use

Use archive docs to understand prior findings, CSS deletion provenance, route
render evidence, or cleanup history. Do not cite archived screenshots or audits
as current UI acceptance.

Current frontend archive lanes:

- `docs/frontend/archive/`: historical frontend docs moved out of active lanes
  during domain consolidation.
- `docs/audits/archive/frontend/`: older DOM, CSS, bundle, route, scroll, and
  old launch UX evidence retained for provenance.
- Historical design-transition provenance is indexed via `docs/ARCHIVE_INDEX.md`
  and retained under current archive lanes when present; do not assume a
  standalone design-archive lane exists here.
