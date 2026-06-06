# T-1078 Scanner explainability consumer readiness audit

Task ID: T-1078-AUDIT

Task title: Scanner explainability consumer readiness audit

Mode: READ-ONLY-AUDIT with one explicitly allowed docs-only audit artifact,
commit, and push.

Allowed artifact:

`docs/codex/audits/T-1078-scanner-explainability-consumer-readiness-audit.md`

Observed workspace:

- cwd:
  `/Users/yehengli/worktrees/t1078-scanner-explainability-consumer-readiness-audit`
- branch: `codex/t1078-scanner-explainability-consumer-readiness-audit`
- pre-write tracked/staged dirty files: none
- after validation-time fetch/checks: local HEAD `117fe4c5`; `origin/main`
  advanced while the audit was running; no merge/rebase was performed
- no branch switch, rebase, merge, source edit, test edit, config edit, API edit,
  provider/cache/runtime edit, frontend behavior edit, or UI implementation was
  performed

Inputs read:

- `AGENTS.md`
- `docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md`
- `docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md`
- `docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md`
- `docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md`
- `docs/codex/audits/T-1047-scanner-score-caps-explainability-readiness-audit.md`
- `docs/codex/audits/T-1062-data-reliability-track-convergence-audit.md`

Scope boundary:

- This audit inspects Scanner backend/API/frontend consumer paths only.
- This audit does not change scanner scoring, score caps, candidate selection,
  ranking, sorting, filtering, degraded semantics, source authority, provider
  runtime, cache behavior, API response behavior, frontend behavior, UI, tests,
  config, package files, lockfiles, portfolio, options, or backtest.
- This audit explicitly rejects raw metadata badge dumps and provider/source
  authority inference.

## Readiness verdict

Scanner explainability metadata is ready for a consumer-safe information
architecture decision, not for a new UI implementation or any scoring/ranking
semantic change.

The current system already has the main metadata needed for safe consumer
consumption:

- score-cap explainability (`raw_score`, `final_score`, `score_delta`,
  `score_cap`, confidence, cap reason, degradation reason, missing evidence);
- source-confidence flags and caps;
- candidate evidence packets with user-facing labels, freshness, quality, and
  warning flags;
- consumer diagnostics that intentionally strip provider/source-authority
  internals;
- candidate evidence/readiness/research summary/source provenance frames;
- frontend TypeScript types and API camelCase conversion that preserve the
  current detail payload.

The remaining risk is not a missing DTO/type lock. The remaining risk is UI
placement and vocabulary: which safe summary belongs in the row, what belongs
inside disclosure/detail, and what must remain admin-only. Therefore the next
safe task should be a frontend IA documentation addendum, not tests-only and not
another DTO/type lock.

Score-cap semantic changes and ranking changes are explicitly rejected. Score
caps are live rank-affecting scanner behavior because the service writes
`candidate["score"] = final_score` after cap application and before shortlist
sorting (`src/services/market_scanner_service.py:6916`,
`src/services/market_scanner_service.py:6922`).

## Metadata inventory

### Backend/service metadata that exists today

- `score_explainability` is built by
  `_apply_score_caps_and_explainability()` with raw/final score, delta, cap,
  confidence, coverage, cap/degradation reasons, cap-applied flag, missing
  evidence, reason codes, score-grade gate, and nested source confidence
  (`src/services/market_scanner_service.py:6835`,
  `src/services/market_scanner_service.py:6925`).
- `source_confidence` is normalized as a source-confidence contract with
  freshness, fallback/stale/partial/synthetic/unavailable flags, confidence
  weight, coverage, cap/degradation reasons, source authority, score
  contribution, observation-only, and proxy flags
  (`api/v1/schemas/scanner.py:204`, `api/v1/schemas/scanner.py:227`).
- `evidence_packet` is attached to shortlist diagnostics and includes
  raw/final score, confidence, evidence coverage, cap/degradation reason,
  freshness/data-quality state, freshness detail, provider observation,
  missing evidence, user-facing labels, warning flags, and admin reason codes
  (`src/services/market_scanner_service.py:7391`,
  `src/services/scanner_evidence_packet.py:456`).
- `consumerDiagnostics` is derived from explainability/evidence packet and
  exposes a consumer-safe projection with status, confidence/freshness
  categories, score-grade gate, cap/degradation reason, source class, missing
  evidence, labels, warning flags, and optional investor signal
  (`api/v1/schemas/scanner.py:286`,
  `src/services/scanner_evidence_packet.py:311`).
- Candidate-level frames exist for evidence coverage, research readiness,
  research summary, and source provenance
  (`api/v1/schemas/scanner.py:347`,
  `src/services/market_scanner_service.py:7339`,
  `src/services/market_scanner_candidate_evidence.py:151`,
  `src/services/market_scanner_candidate_summary.py:140`,
  `src/services/market_scanner_source_provenance_sidecar.py:423`).

### API preservation that exists today

- `POST /api/v1/scanner/run`, `GET /api/v1/scanner/watchlists/today`, and
  `GET /api/v1/scanner/runs/{run_id}` all declare and return
  `ScannerRunDetailResponse` (`api/v1/endpoints/scanner.py:134`,
  `api/v1/endpoints/scanner.py:288`,
  `api/v1/endpoints/scanner.py:371`).
- `ScannerCandidateResponse` preserves `raw_score`, `final_score`,
  `diagnostics`, `consumerDiagnostics`, `candidateEvidenceFrame`,
  `candidateResearchReadiness`, `candidateResearchSummaryFrame`, and
  `candidateSourceProvenanceFrame` (`api/v1/schemas/scanner.py:326`).
- Candidate diagnostics metadata is validated/locked for
  `score_explainability` and `evidence_packet` before response model dump
  (`api/v1/schemas/scanner.py:311`, `api/v1/schemas/scanner.py:353`).
- `ScannerRunHistoryItem` intentionally keeps only run-level summary fields and
  does not carry candidate explainability (`api/v1/schemas/scanner.py:435`).
- `ScannerCandidateDiagnosticsResponse` is a bounded candidate-pool diagnostic
  list and does not preserve full `score_explainability` or `evidence_packet`
  (`api/v1/schemas/scanner.py:383`).

### Frontend preservation that exists today

- `scannerApi.getRun()` converts the route payload with `toCamelCase` and
  returns `ScannerRunDetail`, preserving detail payload shape at the fetch
  boundary (`apps/dsa-web/src/api/scanner.ts:86`).
- Frontend types model `ScannerSourceConfidence`,
  `ScannerScoreExplainability`, `ScannerEvidencePacket`,
  `ScannerConsumerDiagnostics`, `ScannerCandidateEvidenceFrame`,
  `ScannerCandidateResearchSummaryFrame`, and candidate-level provenance
  (`apps/dsa-web/src/types/scanner.ts:197`,
  `apps/dsa-web/src/types/scanner.ts:217`,
  `apps/dsa-web/src/types/scanner.ts:245`,
  `apps/dsa-web/src/types/scanner.ts:309`,
  `apps/dsa-web/src/types/scanner.ts:385`,
  `apps/dsa-web/src/types/scanner.ts:406`,
  `apps/dsa-web/src/types/scanner.ts:425`).
- Frontend API tests preserve score-cap explainability metadata, evidence
  packets, source-confidence flags, consumer diagnostics, result-cap summary,
  and score order after camelCase conversion
  (`apps/dsa-web/src/api/__tests__/scanner.test.ts:139`).

## Metadata flow matrix

| Metadata family | Backend/source | API/detail preservation | Frontend/type preservation | Current UI consumption | Consumer readiness |
| --- | --- | --- | --- | --- | --- |
| Score cap explainability | Built in `_apply_score_caps_and_explainability()` and writes `raw_score`, `final_score`, `score`, `score_explainability` (`src/services/market_scanner_service.py:6916`) | Locked in `ScannerScoreExplainabilityMetadata` and candidate diagnostics validator (`api/v1/schemas/scanner.py:227`, `api/v1/schemas/scanner.py:311`) | Typed as `ScannerScoreExplainability`; API test proves camelCase preservation (`apps/dsa-web/src/types/scanner.ts:217`, `apps/dsa-web/src/api/__tests__/scanner.test.ts:326`) | `ScannerScoreTrustStrip` can read explainability/evidence packet/source confidence, but default ranked rows pass stripped trust sources to avoid raw trust leakage (`apps/dsa-web/src/components/scanner/ScannerScoreTrustStrip.tsx:113`, `apps/dsa-web/src/pages/UserScannerPage.tsx:3302`) | Ready for bounded summary/disclosure language. Not ready for raw cap badges or score semantics changes. |
| Source confidence | Derived from quote/history/snapshot/degraded/proxy state and nested into explainability (`src/services/market_scanner_service.py:6895`) | Locked by `ScannerSourceConfidenceMetadata` (`api/v1/schemas/scanner.py:204`) | Typed as `ScannerSourceConfidence` (`apps/dsa-web/src/types/scanner.ts:197`) | Trust strip localizes only coarse confidence/freshness/observation states (`apps/dsa-web/src/components/scanner/ScannerScoreTrustStrip.tsx:68`, `apps/dsa-web/src/components/scanner/ScannerScoreTrustStrip.tsx:190`) | Consumer UI may show coarse confidence/freshness only. Raw authority flags/source tier/provider identity stay admin-only. |
| Evidence packet | Built for shortlist diagnostics with evidence buckets, labels, warning flags, provider observation, and admin reason codes (`src/services/scanner_evidence_packet.py:456`) | Locked as `ScannerEvidencePacketMetadata` with extra allowed (`api/v1/schemas/scanner.py:261`) | Typed as `ScannerEvidencePacket` with safe known fields and extra fallback (`apps/dsa-web/src/types/scanner.ts:245`) | Candidate evidence strip shows evidence coverage/readiness and provenance summary, not raw packet data (`apps/dsa-web/src/components/scanner/ScannerCandidateEvidenceStrip.tsx:162`) | Ready for disclosure/detail and row-level safe summary. `adminReasonCodes` and provider observation are unsafe for default consumer UI. |
| Consumer diagnostics | Built as consumer-safe projection from evidence/explainability (`src/services/scanner_evidence_packet.py:311`) | Locked as `ScannerConsumerDiagnosticsMetadata` (`api/v1/schemas/scanner.py:286`) | Typed as `ScannerConsumerDiagnostics`; API test covers investor signal and safe fields (`apps/dsa-web/src/types/scanner.ts:309`, `apps/dsa-web/src/api/__tests__/scanner.test.ts:23`) | Used in row/detail safety copy and investor signal rendering (`apps/dsa-web/src/components/scanner/ScannerCandidatePresenters.tsx:335`) | Most ready consumer surface. Use this first before raw diagnostics. |
| Candidate evidence/readiness/summary/provenance frames | Built in public candidate projection and persisted row replay (`src/services/market_scanner_service.py:7297`, `src/services/market_scanner_service.py:7345`) | Preserved as candidate fields (`api/v1/schemas/scanner.py:347`) | Typed in `ScannerCandidate`; page tests assert additive display without order/score changes (`apps/dsa-web/src/types/scanner.ts:453`, `apps/dsa-web/src/pages/__tests__/UserScannerPage.test.tsx:1287`) | Row-level explanation and detail sections already render safe coverage, research summary, and source context (`apps/dsa-web/src/components/scanner/ScannerCandidatePresenters.tsx:753`, `apps/dsa-web/src/components/scanner/ScannerCandidatePresenters.tsx:364`) | Best current basis for consumer UI. Keep row-level and detail-first, no raw badge dump. |
| Candidate diagnostics list | Built as candidate pool diagnostics for selected/rejected/data-failed records (`api/v1/schemas/scanner.py:383`) | Bounded to symbol/name/rank/status/score/provider/reason/failed fields/metrics plus CN observation | `ScannerCandidateDiagnostic.metadata` is generic, but fallback conversion does not carry full explainability (`apps/dsa-web/src/types/scanner.ts:345`, `apps/dsa-web/src/pages/UserScannerPage.tsx:1305`) | Diagnostic candidate detail shows safe rejection/data notes (`apps/dsa-web/src/pages/__tests__/UserScannerPage.test.tsx:3043`) | Not a full explainability carrier. Do not base consumer explainability UI on `candidates[]` metadata. |
| AI interpretation | Raw diagnostics projected by `public_payload_from_diagnostics()` | Public candidate AI field is constrained by schema (`api/v1/schemas/scanner.py:344`) | Typed as `ScannerAiInterpretation` inside candidate | Detail surface renders public AI/commentary only | Use public AI fields only. Raw traces/provider/model failure internals stay hidden. |

## Missing, dropped, or unsafe fields

Missing or intentionally dropped for normal consumer paths:

- `GET /api/v1/scanner/runs` history list does not carry candidate
  explainability; it is only a run summary surface.
- `candidates[]` diagnostic entries are bounded diagnostics and do not carry
  full `score_explainability` or `evidence_packet`.
- `diagnosticToCandidate()` maps diagnostic entries into candidate-shaped UI
  objects with empty `diagnostics` and without `consumerDiagnostics` or
  evidence/provenance frames (`apps/dsa-web/src/pages/UserScannerPage.tsx:1305`,
  `apps/dsa-web/src/pages/UserScannerPage.tsx:1342`).
- `fallbackDiagnosticFromCandidate()` similarly emits empty `metadata`
  (`apps/dsa-web/src/pages/UserScannerPage.tsx:1346`).
- Default ranked rows pass stripped trust sources into `ScannerScoreTrustStrip`
  (`apps/dsa-web/src/pages/UserScannerPage.tsx:358`,
  `apps/dsa-web/src/pages/UserScannerPage.tsx:3302`).
  This is a consumer-safety choice, but it means raw diagnostics are not the row
  explanation source.

Unsafe for default consumer display:

- `diagnostics.cn_provider_observation`
- `diagnostics.evidence_packet.providerObservation`
- `diagnostics.evidence_packet.adminReasonCodes`
- raw provider ids/names/source tier/trust level/source-authority flags
- raw `source_confidence` internals such as `sourceAuthorityAllowed` and
  `scoreContributionAllowed`
- raw AI interpretation traces, fallback flags, provider/model diagnostics, or
  debug references
- backend snake_case field names and reason codes such as provider failure codes

Existing tests already enforce this consumer boundary by proving
`consumerDiagnostics` does not leak provider/source-authority details
(`tests/test_market_scanner_api_contract.py:686`,
`tests/test_market_scanner_api_contract.py:921`) and that source provenance
does not leak raw/internal terms (`tests/test_market_scanner_api_contract.py:832`).

## Consumer UI information architecture decision

Recommended consumer UI pattern:

1. Row-level explanation as the primary layer.
2. A small number of bounded badges/chips only for consumer-safe states such as
   confidence limited, latest available data, partial coverage, observe-only,
   and research-only.
3. A disclosure/detail layer for evidence coverage, research readiness,
   research summary, freshness, and source context after localization.
4. Admin-only detail for raw reason codes, provider/source authority, source
   tier, provider observation, raw diagnostics, traces, debug refs, and
   maintainer vocabulary.

Not recommended:

- raw metadata badges;
- provider/source-authority inference;
- showing provider/source tier as consumer trust badges;
- turning fallback/stale/partial/source-confidence flags into investment
  advice;
- changing score cap math, score labels, row order, candidate selection,
  ranking, sorting, filtering, or degraded defaults.

This matches current UI direction: the conclusion band gives a soft data cue
(`apps/dsa-web/src/components/scanner/ScannerDisplayPanels.tsx:473`), the
ranked row focuses on score/status/key reason/data quality and already has
evidence/research summary slots
(`apps/dsa-web/src/components/scanner/ScannerCandidatePresenters.tsx:722`),
candidate detail shows evidence coverage safely
(`apps/dsa-web/src/components/scanner/ScannerCandidatePresenters.tsx:364`), and
secondary disclosures keep broader data notes collapsed by default
(`apps/dsa-web/src/pages/UserScannerPage.tsx:3420`).

## Current tests guarding score/order/cap behavior

Score and order:

- `test_prepare_shortlist_sorts_by_score_then_symbol_and_assigns_rank_before_ai`
  locks sort order as score desc, symbol asc, with rank assigned before AI
  (`tests/test_market_scanner_service.py:1651`).
- API tests preserve selected and shortlist signatures with symbol/rank/score/
  raw/final score (`tests/test_market_scanner_api_contract.py:356`,
  `tests/api/test_scanner.py:207`).
- Golden fixture tests require candidate score/raw/final score fields and
  assert public score equals final score
  (`tests/test_scanner_golden_contracts.py:47`,
  `tests/test_scanner_golden_contracts.py:139`).

Score caps and degraded source-confidence:

- fallback cap, degraded snapshot cap, degraded token vocabulary, stale/partial
  cap, public proxy cap, and authorized non-proxy no-cap tests are covered in
  `tests/test_market_scanner_service.py:1780`,
  `tests/test_market_scanner_service.py:1835`,
  `tests/test_market_scanner_service.py:1893`,
  `tests/test_market_scanner_service.py:2135`,
  `tests/test_market_scanner_service.py:2227`, and
  `tests/test_market_scanner_service.py:2301`.
- degraded snapshot runtime path locks fallback/degraded behavior and caps
  shortlist scores to `<= 40.0`
  (`tests/test_market_scanner_service.py:3204`).
- source-confidence contract tests prevent degraded sources from masquerading
  as live/fresh and keep cap vocabulary aligned with score-grade authority
  gates (`tests/test_source_confidence_contract.py:137`,
  `tests/test_source_confidence_contract.py:213`).

Additive metadata without score/order drift:

- evidence packet attachment is tested without extra provider calls and with
  persisted replay (`tests/test_market_scanner_service.py:2357`).
- factor observations do not mutate score/rank
  (`tests/test_market_scanner_service.py:2409`).
- CN provider observation and Baostock observation sidecars do not mutate
  score/rank (`tests/test_market_scanner_service.py:3392`,
  `tests/test_market_scanner_service.py:3490`,
  `tests/test_market_scanner_service.py:3818`).
- API tests preserve provider observation metadata, candidate evidence/readiness
  fields, candidate provenance, and safe consumer diagnostics
  (`tests/test_market_scanner_api_contract.py:562`,
  `tests/test_market_scanner_api_contract.py:703`,
  `tests/test_market_scanner_api_contract.py:841`).
- Frontend API tests preserve score-cap explainability metadata, result-cap
  summary, evidence packet, source-confidence flags, consumer diagnostics, and
  candidate score order after camelCase conversion
  (`apps/dsa-web/src/api/__tests__/scanner.test.ts:139`).
- Frontend page tests cover candidate evidence/research/provenance display
  without order or score-label changes and without raw/internal leakage
  (`apps/dsa-web/src/pages/__tests__/UserScannerPage.test.tsx:1287`,
  `apps/dsa-web/src/pages/__tests__/UserScannerPage.test.tsx:1342`,
  `apps/dsa-web/src/pages/__tests__/UserScannerPage.test.tsx:1388`,
  `apps/dsa-web/src/pages/__tests__/UserScannerPage.test.tsx:1855`).

## Recommended next task

Exactly one safe next task:

**T-1078-M1: Scanner explainability consumer IA addendum**

Classification: frontend IA doc, docs-only.

Recommended future allowed file:

- `docs/frontend/WOLFYSTOCK_CONSUMER_DATA_QUALITY_UX.md`

Goal:

- Add a Scanner-specific IA addendum to the existing consumer data-quality UX
  contract.
- Define which fields feed row-level explanation, disclosure/detail, and
  admin-only detail.
- Define safe vocabulary for score-cap/fallback/stale/partial/observe-only
  states.
- Require existing ranking/score/order semantics to remain unchanged for any
  future implementation.

Why this is the right next task:

- DTO/type lock is already materially present across backend schema, API
  response models, frontend types, and frontend API tests.
- Tests already guard the main score/order/cap and consumer leakage boundaries.
- The unresolved decision is information architecture and copy hierarchy, not
  metadata existence.
- A docs-only IA addendum avoids overlap with Windows React Doctor or
  route-smoke work and prevents a future UI task from turning raw metadata into
  badges.

Future task acceptance criteria:

- The Scanner section names the allowed consumer layers:
  row-level summary, disclosure/detail, admin-only.
- The addendum forbids raw provider/source-authority/admin reason-code display
  on consumer surfaces.
- The addendum explicitly says score cap/ranking/filtering semantics are out of
  scope.
- The addendum references existing safe surfaces:
  `consumerDiagnostics`, `candidateEvidenceFrame`,
  `candidateResearchReadiness`, `candidateResearchSummaryFrame`, and
  `candidateSourceProvenanceFrame`.

Not recommended as the next task:

- tests-only task: useful after an implementation plan exists, but current
  risk is UI hierarchy, not missing guard coverage;
- DTO/type lock: already sufficiently present for IA planning;
- frontend implementation: premature until IA/copy/display boundaries are
  written;
- backend/API/provider/cache/source-authority work: protected-domain adjacent
  and unnecessary for consumer IA;
- score-cap, score/rank/order/filter/cap/degraded semantic changes: explicitly
  rejected.

## Future protected-domain warnings

Future tasks must stop or seek explicit authorization before touching:

- scanner scoring math, score components, cap weights, cap reasons, cap
  precedence, `raw_score`, `final_score`, or `score`;
- shortlist membership, candidate selection, rank assignment, sort order,
  tie-breaks, thresholds, filters, result caps, or degraded-mode defaults;
- provider adapters, provider order, live-call paths, fallback behavior,
  freshness/live labeling, source authority, cache, MarketCache TTL/SWR/cold
  start behavior, or payload meaning;
- API response semantics beyond explicitly additive contract documentation;
- frontend logic that reorders rows, hides rows, changes scores, changes
  filters, or displays explainability as investment/trading advice;
- portfolio, options, backtest, auth/RBAC, notification, AI prompt/model, or
  runtime provider/cache domains.

## Current audit validation plan

Required validation for this docs-only audit:

```bash
git diff --check
./scripts/release_secret_scan.sh
```

Expected final diff:

- only
  `docs/codex/audits/T-1078-scanner-explainability-consumer-readiness-audit.md`

No full backend/frontend test suite is required for this report-only task.

## Final audit decision

Proceed with exactly one future docs-only IA task:

**T-1078-M1: Scanner explainability consumer IA addendum** in
`docs/frontend/WOLFYSTOCK_CONSUMER_DATA_QUALITY_UX.md`.

Defer all source, test, API, provider/cache/runtime, frontend implementation,
portfolio/options/backtest, and score/ranking/cap/degraded semantic changes.

Final diff confirmation for this audit:

- docs-only report artifact;
- no source files changed;
- no tests changed;
- no config/package/lockfile changes;
- no API behavior changed;
- no provider/cache/runtime behavior changed;
- no frontend behavior or UI implementation changed;
- no raw metadata badge dump added;
- no provider/source-authority inference added;
- no scanner score/ranking/filtering/cap/degraded semantic change;
- no portfolio/options/backtest change.
