# Options Authority Onboarding Track Status

Status: observation-only onboarding index; no repo-local Options authority source currently feasible
Scope: expiration-calendar, event-calendar, and IV-rank authority onboarding tracks
Non-goal: no authority grant, no provider integration, no runtime/gate/API change

## Purpose

This index summarizes which observation-only onboarding artifacts already exist, which inert scaffolding is still missing, and which manual external verification blockers remain before any future source onboarding work can be reconsidered.

All three tracks remain non-authoritative. No current repo-local provider or source can be treated as Options authority. Current artifacts are diagnostic-only and must not be used for gates, recommendations, `decisionGrade`, provider routing, budgets, API behavior, or live-call enablement. Any future authority requires manual external verification first and then a separate dedicated policy task.

## Track Status

| Surface | Observation-only status | Current artifact status | External blocker |
| --- | --- | --- | --- |
| `expiration-calendar` | Closest future onboarding candidate, still observation-only | Full observation-only scaffold exists end to end, but no authority path is feasible yet | Manual external verification for provenance, rights, freshness, coverage, taxonomy, and adjusted deliverables still missing |
| `event-calendar` | Observation-only | Gap + registry + helper/runtime projection scaffolding remain diagnostic-only; no runtime-safe candidate-evidence artifact exists | Manual external verification for provenance, official backing, rights, freshness, taxonomy, confirmation, timezone/session, and coverage still missing |
| `IV-rank` | Observation-only | Gap contract + registry metadata + worksheet exist; compact operator-summary coverage is observation-only and not authority | Manual external verification for provenance, rights, freshness, methodology, universe, and missing-data policy still missing |

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
  - live/delayed, production/sandbox, freshness/SLA/max-age facts
  - coverage universe and venue scope facts
  - expiration taxonomy plus adjusted-deliverable/corporate-action proof
- Still forbidden:
  - any authority grant
  - any provider or live-call onboarding
  - any provider/source authority label
  - any provider routing, budget, or live-call enablement
  - any gate, recommendation, `decisionGrade`, or API change

### `event-calendar`

- Complete observation-only scaffolding:
  - gap contract
  - registry metadata
  - helper/runtime projection scaffolding
  - external verification worksheet
- Missing scaffolding:
  - source-candidate evidence packet/contract as a runtime-safe artifact
  - evidence runtime projection
- External verification still required:
  - source identity and provenance chain
  - licensed provider / exchange / issuer / official-calendar backing
  - entitlement, redistribution, and decision-use rights
  - live/delayed, production/sandbox, freshness/SLA/max-age facts
  - coverage universe facts
  - event taxonomy, confirmation, timezone/session, and event identity facts
- Still forbidden:
  - any authority grant
  - any provider or live-call onboarding
  - any provider/source authority label
  - any provider routing, budget, or live-call enablement
  - any gate, recommendation, `decisionGrade`, or API change

### `IV-rank`

- Complete observation-only scaffolding:
  - gap contract
  - registry metadata
  - compact operator-summary coverage for candidate gap and registry metadata
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
  - live/delayed, production/sandbox, freshness/SLA/max-age facts
  - coverage universe facts
  - methodology, rank/percentile definition, lookback/date range, calculation basis
  - contract universe, moneyness/expiry rules, missing-data policy, and coverage facts
- Still forbidden:
  - any authority grant
  - any provider or live-call onboarding
  - any provider/source authority label
  - any provider routing, budget, or live-call enablement
  - any gate, recommendation, `decisionGrade`, or API change

## Naming / Parity Risks

- Worksheet vs packet terminology:
  - `expiration-calendar` doc is framed as a packet and also contains a worksheet section; `event-calendar` and `IV-rank` are worksheet-first docs. Keep future references explicit about whether the target is a doc worksheet or a runtime-safe candidate-evidence artifact. None of these terms imply authority feasibility by themselves.
- Registry vs policy candidate naming:
  - policy gap contracts use surface-level candidate source classes; registry metadata uses source keys such as `options_lab.event_calendar_candidate_evidence`. Do not treat those names as interchangeable identifiers.
- Helper reason codes vs source-candidate family names:
  - authority helpers emit non-authority reason codes, while gap contracts and registry metadata enumerate evidence families. They should stay aligned conceptually, but one is explanatory output and the other is onboarding requirements. Helper/runtime projection presence must not be read as source authority.

## Safe Future Sequence

1. Complete manual external verification first.
2. Update docs with verified source facts only.
3. Run a read-only implementation audit.
4. Finish missing inert scaffolding only if still justified.
5. Only then consider an inert provider/source adapter.
6. Reserve authority grants for a separate future policy task.

## Locked Boundaries

- No runtime behavior changes.
- No source code changes.
- No tests changed.
- No provider/source authority upgrade.
- No provider routing/budget/live-call behavior changes.
- No gate/recommendation/`decisionGrade`/API behavior changes.
- No live calls.
- No broker/order/trading/portfolio mutation.
