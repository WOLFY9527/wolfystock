# DATA-035 Scenario Durable Baseline Snapshot Plan

Task ID: DATA-035

This document is a planning artifact only. It maps the current Scenario Lab
baseline-readiness boundary and defines the implementation sequence needed to
create durable Scenario baseline snapshots in a later protected-domain task.

## 1. Executive conclusion

Scenario Lab can currently prove that the backend contract separates usable
baseline inputs from missing, request-supplied, stale, sample, static, or
fallback inputs. The deterministic engine accepts caller-supplied market regime
evidence or driver scores, returns `baselineReadiness`, and fails closed unless
baseline snapshot state, market frame state, driver input coverage, evidence
completeness, and source authority all support the stronger baseline-readiness
state. The API route is `POST /api/v1/market/scenario-lab`, the schema owner is
`api/v1/schemas/market_scenario_lab.py`, and the engine owner is
`src/services/market_scenario_lab_engine.py`.

Durable baseline snapshots matter for professional research because a scenario
comparison is only useful when the base inputs can be reproduced, audited,
aged, and tied back to accepted market and portfolio evidence. A scenario run
that only receives request-supplied driver scores can still be a bounded
research observation, but it cannot prove that the comparison was made from a
stored baseline that existed in the target environment at a known market
session.

This task does not implement storage yet. The current allowed edit scope is
this document only, and the real implementation would cross protected domains:
DB migrations or storage code, API contract expansion, Scenario UI readback,
target-environment evidence collection, and possibly provider cache/runtime
read paths. Those changes need their own explicit task, focused tests, and
post-change browser acceptance.

## 2. Current baseline readiness flow

The Scenario Lab flow is currently request/snapshot driven:

1. `api/v1/endpoints/market.py` receives `MarketScenarioLabRequest`.
2. `MarketScenarioLabRequest` accepts `baseRegime` / `baseDecision`,
   `driverScores`, scenario name or preset, and scenario overrides.
3. The endpoint calls `build_market_scenario_lab()` with those request fields.
4. `MarketScenarioLabEngine.build()` normalizes the supplied base inputs,
   applies deterministic scenario shocks, and returns an observation-only
   research payload with `baselineReadiness`.

Baseline snapshot state:

- The engine reads `baseDecision.baselineSnapshot`,
  `baseDecision.baselineMarketSnapshot`, or `baseDecision.snapshot`.
- `_baseline_snapshot_component()` normalizes the component state.
- If the whole data state is unavailable, the baseline snapshot becomes
  `missing`.
- If the component is available but source authority is not allowed, or the
  data state is not `real_cached`, the component is downgraded to `partial`.
- A stale marker on the component remains visible as a degraded component state
  rather than being hidden.

Market frame state:

- The engine reads `baseDecision.marketFrame` or
  `baseDecision.currentMarketFrame`.
- If no explicit frame exists, a base regime plus at least three scoring
  drivers lets the engine treat the market frame as available.
- Missing regime evidence makes the frame missing.
- Stale markers in the frame or data quality downgrade the frame to stale.

Driver input state:

- The fixed driver set is `dealerGamma`, `breadthParticipation`,
  `volatilityStructure`, `ratesDollar`, `liquidityCredit`, `crossAssetRisk`,
  `sectorThemeRotation`, and `eventCatalyst`.
- `score_grade`, `ready`, `available`, or a non-zero score count as available
  driver evidence.
- `limited`, `partial`, `degraded`, or `stale` count as partial driver
  evidence.
- Any other state is missing.
- Fewer than three scoring drivers makes the driver-input component missing.

Evidence completeness:

- `_evidence_completeness_component()` aggregates baseline snapshot gaps,
  market frame gaps, affected driver keys, scenario data boundary gaps, score
  authority gaps, and evidence-limit gaps.
- Any missing core component blocks readiness.
- Non-blocking gaps make readiness partial.
- Only a gap-free result is ready.

Source authority:

- `_base_from_inputs()` reads `sourceAuthorityAllowed`,
  `scoreAuthorityAllowed`, `dataQuality.sourceAuthorityAllowed`,
  `dataQuality.scoreAuthorityAllowed`, or
  `dataQuality.scoreContributionAllowed`.
- `sourceAuthorityAllowed` is a boolean gate; it is not a source-lineage
  record and does not prove that a target environment has stored inputs.
- `scoreAuthority` becomes `authoritative` only when evidence completeness is
  ready and source authority is allowed.

Sample, fallback, and demo state:

- Scenario input can mark `dataSourceClass`, `sourceClass`, `fixtureMode`,
  `demoMode`, or `sampleData`.
- Fixture, demo, and sample sources become `demo_static_sample`.
- Static and fallback sources become sample states such as `static` or
  `fallback`.
- These states keep the baseline partial or blocked and observation-only; they
  must never be promoted into the stronger baseline state.

Observation-only vs authoritative state:

- The top-level Scenario Lab payload remains `observationOnly=true` and
  `decisionGrade=false`.
- The nested `baselineReadiness` packet can mark the baseline itself as
  `authoritative=true` only for a complete, source-authority-allowed,
  `real_cached` input set.
- A "real cached authoritative baseline" in current code means: supplied base
  inputs with `dataSourceClass` or equivalent source class normalized into the
  real/cached set, `sourceAuthorityAllowed=true`, available baseline snapshot,
  available market frame, available driver inputs, ready evidence completeness,
  no evidence-limit gaps beyond the generic boundary, and no sample/fallback
  state. It does not mean the engine proved persistence by itself.

Current UI/API wiring gap:

- The frontend API type can receive `baselineReadiness` and map it into
  consumer-safe labels.
- The current Scenario Lab page path derives base inputs from Decision Cockpit
  and mainly forwards regime, confidence, confidence score, and driver scores.
- That path does not yet read a durable baseline snapshot ID or pass stored
  baseline lineage back to the endpoint, so normal page usage remains
  request-supplied or observation-only unless a caller supplies the richer
  baseline object.

## 3. Durable baseline requirements

A durable Scenario baseline should contain the following fields or equivalent
contract concepts.

Snapshot identity:

- Stable `baselineSnapshotId`.
- Stable `scenarioRunId` when a scenario output is persisted.
- Scope keys such as market scope, portfolio/account scope if applicable,
  scenario family, and engine version.
- Input snapshot references for market, macro, ETF/index/proxy, and portfolio
  components.

Timestamp and market session:

- `createdAt` for when the durable row or artifact was written.
- `asOf` for the market evidence timestamp.
- Market session label such as pre-market, regular, post-market, close, or
  official daily row.
- Time zone and date normalization rules.

Source lineage:

- Consumer-safe source family names rather than raw provider diagnostics.
- Internal source reference IDs kept for admin/operator evidence only.
- Source authority and score-contribution status for each required input
  family.
- Sanitized reason codes for partial, stale, missing, or blocked families.

Freshness window:

- Per-family freshness thresholds for intraday market proxies, daily official
  macro rows, weekly liquidity rows, portfolio snapshots, and option/gamma
  observations if later connected.
- Explicit stale markers when any input falls outside its window.
- No hidden refresh that upgrades an old stored snapshot during readback.

Market frame inputs:

- Base regime and confidence.
- Current market frame component state.
- Evidence gaps and affected frame components.
- Source authority and freshness state for the frame.

Driver inputs:

- Baseline driver values for the fixed driver set.
- Driver evidence state for each key.
- Driver source family or input reference.
- Driver missing/partial state and affected keys.

Macro, ETF, index, and proxy inputs:

- Official volatility and rates rows where available.
- Index or ETF proxy quote snapshots with delay/freshness labels.
- Liquidity, breadth, cross-asset, and sector/theme rotation references.
- Explicit proxy markers when the source is proxy-only or sample-limited.

Evidence completeness:

- Baseline snapshot component state.
- Market frame component state.
- Driver input component state.
- Evidence completeness state and gaps.
- Source authority allowed flag and score authority state.

Stale, missing, and fallback markers:

- Stale flags per component and per input family.
- Missing-family list.
- Fallback/static/sample/fixture markers.
- Blocked vs partial reason summary.

Reproducibility:

- Engine version.
- Schema version.
- Deterministic scenario name and overrides.
- Request hash or input hash.
- Output hash for stored result replay comparison.

Audit trail:

- Actor or service principal that created the baseline.
- Target environment label without secrets.
- Creation command/probe version for operator artifacts.
- Sanitized validation status.
- Linkage to accepted evidence artifacts when available.

Retention rules:

- Short retention for intraday market proxy inputs.
- Longer retention for official daily macro rows and scenario run summaries.
- Explicit purge policy for raw provider payloads if they are ever stored
  elsewhere.
- No raw secrets, credentials, headers, cookies, request URLs with tokens, or
  raw provider payloads in the Scenario baseline record.

Target-environment evidence artifact:

- A sanitized JSON or Markdown artifact proving that the target environment had
  at least one real cached baseline input set.
- It should include snapshot IDs, as-of timestamps, source family states,
  freshness states, missing/stale markers, and the Scenario Lab readiness
  projection.
- It should omit provider credentials, raw payloads, request IDs, trace IDs,
  cache keys, stack traces, and account-private raw data.
- It should state whether the evidence is local-only, staging, or another
  target environment.

## 4. Storage and implementation options

| Option | Pros | Cons | Protected-domain risk | Validation needs | Private-beta suitability |
| --- | --- | --- | --- | --- | --- |
| DB table | Strong durability, queryable readback, stable IDs, audit trail, retention policy, and scenario run linkage. Can model `baselineSnapshotId`, input snapshot refs, owner/scope, schema version, and output hash. | Requires migration/storage design and careful compatibility. Risk of storing too much source detail if the schema is not sanitized. | High: DB migrations, storage code, API readback, and retention behavior. | Migration tests, repository read/write tests, endpoint readback tests, fail-closed missing/stale tests, secret scan, and no-advice guards. | Best long-term fit once protected-domain implementation is approved. |
| Existing cache layer | Lowest immediate runtime overhead. Reuses `MarketCache` TTL/SWR and Market Overview last-known-good behavior. Useful as a hot-path source for current market panel payloads. | Cache freshness is not source authority. Process-local cache can be absent after restart. Cache keys and runtime status are not a durable research contract. | Medium to high: MarketCache TTL/SWR/cold-start behavior and provider cache/runtime semantics must not change by accident. | Cache/freshness tests proving no TTL/SWR semantic change, read-only adapter tests, and stale/fallback projection tests. | Useful as an input source, not sufficient as the durable baseline by itself. |
| Local file artifact | Simple for a non-DB operator proof. Can be generated from existing safe projections and attached to acceptance evidence without changing runtime storage. | Not a product read model. File paths are environment-specific. Harder to enforce retention, ownership, concurrency, and readback semantics. | Low if artifact-only and docs/scripts are explicitly scoped; medium if runtime starts reading files. | Artifact schema test, secret scan, deterministic fixture test, and target-environment probe dry run. | Good as a first evidence step before DB work; not enough for product readback. |
| Hybrid cache plus DB summary | Keeps cache as hot source and last-known-good input while storing a sanitized durable Scenario summary with stable IDs and lineage. Avoids storing raw provider payloads in the Scenario table. | More design work than either cache-only or DB-only. Requires clear boundary between cache payloads, source refs, and consumer-safe summary. | High but controlled: storage/API/schema plus careful no-change guard for provider runtime and MarketCache semantics. | DB/repository tests, cache no-change tests, endpoint readback tests, target-environment evidence artifact, browser acceptance, secret scan, and no-advice guards. | Recommended path for private beta after a protected-domain task authorizes storage. |
| Request-supplied baseline only | Already supported. Safe fail-closed behavior exists. No storage migration or runtime cache dependency. | Cannot prove durable target-environment baselines. Cannot provide snapshot IDs, replayable readback, retention, or operator evidence. | Low for current contract, but it does not solve DATA-035. | Existing engine/API/frontend tests plus negative checks for request-supplied observation-only state. | Acceptable only for bounded demos and research planning, not enough for durable baseline acceptance. |

Recommended option: hybrid cache plus DB summary, preceded by a minimal
non-DB artifact exporter if the team wants target-environment proof before
opening DB migration scope.

## 5. Recommended implementation sequence

1. DATA-035A - Minimal baseline evidence artifact exporter.
   - Scope: add a read-only script or admin-safe diagnostic that projects the
     current Scenario baseline readiness from existing request/snapshot inputs
     into a sanitized artifact.
   - Purpose: prove the artifact shape and target-environment evidence
     contract without DB migrations.
   - Validation: artifact schema test, secret scan, no raw provider/cache/runtime
     token scan, and a dry-run artifact from local safe inputs.

2. DATA-035B - Durable baseline schema contract.
   - Scope: define additive backend schema models for durable baseline summary,
     input snapshot references, source lineage summary, freshness window, and
     scenario run linkage.
   - Purpose: lock field names before storage work.
   - Validation: schema serialization tests, fail-closed sample/fallback/stale
     examples, and no-advice wording guard.

3. DATA-035C - Storage implementation in a protected-domain task.
   - Scope: add DB migration/storage model/repository for sanitized Scenario
     baseline summaries and scenario run records.
   - Purpose: create durable IDs, readback, retention fields, and audit trail.
   - Validation: migration test, repository create/read/update tests,
     idempotency/readback tests, retention tests, and `git diff --check`.

4. DATA-035D - Baseline projection service and endpoint readback.
   - Scope: add a service that converts accepted market/portfolio input
     snapshots into the existing engine's `baseDecision` shape, and add
     additive API fields or a read endpoint for durable baseline readback.
   - Purpose: let Scenario Lab run from a stored baseline instead of relying
     only on request-supplied driver scores.
   - Validation: endpoint tests for latest-baseline readback, missing baseline,
     stale baseline, sample/fallback downgrade, and source-authority failure.

5. DATA-035E - Target-environment baseline probe.
   - Scope: run a sanitized probe that records whether real cached inputs exist
     in the target environment and writes the accepted evidence artifact.
   - Purpose: close the DATA-021 gap without exposing secrets or raw payloads.
   - Validation: probe output schema test, secret scan, target artifact review,
     and explicit blocked status when inputs are missing.

6. DATA-035F - Scenario UI readback.
   - Scope: update Scenario Lab frontend API/page to read the durable baseline
     summary and show consumer-safe readiness/readback state.
   - Purpose: make the visible Scenario Lab path use the stored baseline rather
     than only Decision Cockpit driver-score forwarding.
   - Validation: frontend API normalization tests, Scenario page tests, raw
     internal wording guards, typecheck, and build.

7. DATA-035G - Browser acceptance with populated target data.
   - Scope: browser smoke over Scenario Lab using accepted target-environment
     baseline evidence.
   - Purpose: prove the user-visible page shows useful facts, missing-evidence
     boundaries, and no raw provider/runtime diagnostics.
   - Validation: Playwright route smoke with controlled target data, screenshot
     review, no console/page errors, and no forbidden wording scan.

## 6. Fail-closed and no-fake-data rules

- No synthetic baselines. If a baseline was generated from a fixture, demo,
  sample, static, or fallback source, it must stay marked as sample/fallback
  state and observation-only.
- No fake market frames. If market frame inputs are missing, stale, or only
  inferred from request values, the frame must remain missing, stale, partial,
  or request-supplied.
- No invented driver values. Driver values must come from stored input
  snapshots, explicit request values, or accepted projections. Missing drivers
  remain missing.
- No hidden fallback promoted as authoritative. Static, fallback, proxy-only,
  stale, partial, unavailable, mock, fixture, or synthetic input cannot become
  a stronger baseline state through UI copy or API normalization.
- Stale inputs remain stale. Readback must not silently refresh or relabel old
  stored inputs while presenting them as current.
- Request-supplied inputs remain observation-only unless they reference an
  accepted durable baseline snapshot with source authority and freshness proof.
- Consumer output must remain research context only. It must not imply
  personalized execution instructions, portfolio mutation, broker order entry,
  or decision-grade output.
- Target-environment evidence must be sanitized. It must not include secrets,
  credentials, raw provider payloads, cache keys, request IDs, trace IDs,
  stack traces, or account-private raw records.

## 7. Protected-domain checklist

The later implementation must be split by protected domain. This task only
plans those boundaries.

DB migrations:

- Future task: DATA-035C.
- Touches: DB migration files, storage model, repository methods, retention
  fields, readback tests.
- Guard: do not combine with provider runtime changes or UI readback unless the
  task explicitly expands scope.

Provider cache/runtime:

- Future task: DATA-035D only if the baseline projection reads existing cache or
  Market Overview snapshot seams.
- Touches: read-only adapter around existing cache/snapshot output.
- Guard: do not change provider order, live-call paths, TTL/SWR behavior,
  cold-start behavior, fallback labels, cache keys, or raw payload handling.

External network behavior:

- Future task: DATA-035E only if a target-environment probe is explicitly
  authorized to inspect configured data availability.
- Touches: probe command and sanitized evidence artifact.
- Guard: no new provider calls, broad fanout, quota spending, credential
  logging, or network dependency unless that task says so explicitly.

Source authority scoring:

- Future task: DATA-035B or DATA-035D.
- Touches: additive source-lineage summary and readiness projection.
- Guard: do not relax source authority, score contribution, freshness,
  confidence, or evidence completeness gates.

API schema:

- Future task: DATA-035B or DATA-035D.
- Touches: additive Pydantic schema fields or readback endpoint.
- Guard: preserve current Scenario Lab request/response compatibility and keep
  raw provider/cache/runtime fields out of the consumer response.

Frontend display:

- Future task: DATA-035F and DATA-035G.
- Touches: `apps/dsa-web/src/api/scenarioLab.ts`,
  `apps/dsa-web/src/pages/ScenarioLabPage.tsx`, and focused tests.
- Guard: consumer copy must show compact readiness/readback state without raw
  internal terms, and browser acceptance must prove no accidental
  recommendation or execution implication.
