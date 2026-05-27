# Options Authority Onboarding Track Status

Status: observation-only onboarding index
Scope: expiration-calendar, event-calendar, and IV-rank authority onboarding tracks
Non-goal: no authority grant, no provider integration, no runtime/gate/API change

## Purpose

This index summarizes which observation-only onboarding artifacts already exist, which inert scaffolding is still missing, and which external blockers remain before any future source onboarding work can be reconsidered.

All three tracks remain non-authoritative. Current artifacts are diagnostic-only and must not be used for gates, recommendations, `decisionGrade`, provider routing, API behavior, or live-call enablement.

## Track Status

| Surface | Observation-only status | Current artifact status | External blocker |
| --- | --- | --- | --- |
| `expiration-calendar` | Most complete | Full observation-only scaffold exists end to end | Source/license/use-rights verification still missing |
| `event-calendar` | Partial but close | Gap + registry + runtime projections exist; candidate-evidence contract/runtime projection still missing | Source/license/use-rights verification still missing |
| `IV-rank` | Earlier but no longer gap-only | Gap contract + registry metadata + worksheet exist; compact operator-summary rows now cover candidate gap/registry metadata, but no standalone runtime candidate sections or evidence packet exist | Source/license/use-rights + methodology verification still missing |

## Per Surface

### `expiration-calendar`

- Complete observation-only scaffolding:
  - gap contract
  - registry metadata
  - runtime gap projection
  - registry runtime projection
  - source-candidate evidence packet
  - evidence runtime projection
  - external verification worksheet
- Missing scaffolding:
  - none inside the current observation-only scaffold set
- External verification still required:
  - source identity and provenance chain
  - OCC/OPRA/exchange/licensed-source backing
  - entitlement, redistribution, and decision-use rights
  - live/delayed, production/sandbox, freshness/SLA facts
  - expiration taxonomy plus adjusted-deliverable/corporate-action proof
- Still forbidden:
  - any authority grant
  - any provider or live-call onboarding
  - any gate, recommendation, `decisionGrade`, API, or routing change

### `event-calendar`

- Complete observation-only scaffolding:
  - gap contract
  - registry metadata
  - runtime gap projection
  - registry runtime projection
  - external verification worksheet
- Missing scaffolding:
  - source-candidate evidence packet/contract as a runtime-safe artifact
  - evidence runtime projection
- External verification still required:
  - source identity and provenance chain
  - licensed provider / exchange / issuer / official-calendar backing
  - entitlement, redistribution, and decision-use rights
  - live/delayed, production/sandbox, freshness/SLA facts
  - event taxonomy, confirmation, timezone/session, event identity, and coverage facts
- Still forbidden:
  - any authority grant
  - any provider or live-call onboarding
  - any gate, recommendation, `decisionGrade`, API, or routing change

### `IV-rank`

- Complete observation-only scaffolding:
  - gap contract
  - registry metadata
  - compact operator-summary row coverage for candidate gap and registry metadata
  - external verification worksheet
- Missing scaffolding:
  - standalone runtime gap projection
  - standalone registry runtime projection
  - source-candidate evidence packet as a runtime-safe artifact
  - evidence runtime projection
- External verification still required:
  - source identity and provenance chain
  - provider-reported IV-rank/percentile or approved historical option-IV series proof
  - entitlement, redistribution, and decision-use rights
  - live/delayed, production/sandbox, freshness/SLA facts
  - methodology, rank/percentile definition, lookback/date range, calculation basis
  - contract universe, moneyness/expiry rules, missing-data policy, and coverage facts
- Still forbidden:
  - any authority grant
  - any provider or live-call onboarding
  - any gate, recommendation, `decisionGrade`, API, or routing change

## Naming / Parity Risks

- Worksheet vs packet terminology:
  - `expiration-calendar` doc is framed as a packet and also contains a worksheet section; `event-calendar` and `IV-rank` are worksheet-first docs. Keep future references explicit about whether the target is a doc worksheet or a runtime-safe candidate-evidence artifact.
- Registry vs policy candidate naming:
  - policy gap contracts use surface-level candidate source classes; registry metadata uses source keys such as `options_lab.event_calendar_candidate_evidence`. Do not treat those names as interchangeable identifiers.
- Helper reason codes vs source-candidate family names:
  - authority helpers emit non-authority reason codes, while gap contracts and registry metadata enumerate evidence families. They should stay aligned conceptually, but one is explanatory output and the other is onboarding requirements.

## Safe Future Sequence

1. Finish missing inert scaffolding only.
2. Verify external source, license, and use-rights facts.
3. Update docs with verified source facts only.
4. Run a read-only implementation audit.
5. Only then consider an inert provider/source adapter.
6. Reserve authority grants for a separate future policy task.

## Locked Boundaries

- No runtime behavior changes.
- No source code changes.
- No tests changed.
- No provider/source authority upgrade.
- No gate/recommendation/`decisionGrade`/API behavior changes.
- No live calls.
- No broker/order/trading/portfolio mutation.
