# T-1215 Scanner to Watchlist opportunity pipeline audit

Task ID: T-1215

Task title: Scanner to Watchlist opportunity pipeline audit

Mode: READ-ONLY-AUDIT with one explicitly allowed audit artifact.

Allowed artifact:

`docs/codex/audits/T-1215-scanner-watchlist-pipeline-audit.md`

Observed workspace:

- cwd: `C:\Users\leeyi\worktrees\t1215-scanner-watchlist-pipeline-audit`
- branch: `codex/t1215-scanner-watchlist-pipeline-audit`
- base commit inspected: `5b9567d45f03bef7c112e290f73784aff7e60b5e`
- pre-write tracked/staged dirty files: none
- no branch switch, worktree creation, source edit, config edit, package edit,
  API/schema edit, provider/cache/runtime edit, DB/migration edit, frontend
  behavior edit, or scanner ranking/scoring change was performed

## Verdict

Scanner already emits enough metadata to start a safe Watchlist research
handoff, but the add-to-Watchlist write path persists only a small identity and
score snapshot. The safest v1 is not a new scoring or ranking path. It is a
lineage-preserving, observation-only read projection:

- keep the Watchlist create payload narrow;
- require `scanner_run_id + symbol + market` as the stable lineage pointer;
- read Scanner candidate diagnostics from existing persisted scanner rows;
- project only consumer-safe research fields into Watchlist UI;
- hide raw provider/source authority details and admin reason codes by default;
- block score-grade wording whenever source authority, score contribution,
  freshness, coverage, or degraded-state metadata is missing or limited.

The current gap is therefore a product/lineage projection gap, not a ranking
math gap.

## 1. Current scanner output metadata

### Run-level metadata

Scanner run detail responses include:

- identity: `id`, `market`, `profile`, `profile_label`;
- timing: `run_at`, `completed_at`, `watchlist_date`, `trigger_mode`;
- universe context: `universe_name`, `universe_type`, `theme_id`,
  `theme_label`, requested/accepted/rejected symbol counts;
- run sizing: `shortlist_size`, `universe_size`, `preselected_size`,
  `evaluated_size`;
- summaries: `source_summary`, `headline`, `universe_notes`,
  `scoring_notes`;
- diagnostics: run `diagnostics`, `scannerContextFrame`, notification state,
  comparison to previous run, review summary, theme diagnostics, and candidate
  pool summary.

Evidence:

- `api/v1/schemas/scanner.py:397` defines `ScannerRunDetailResponse`.
- `src/storage.py:1669` stores `MarketScannerRun` with source, summary,
  diagnostics, universe notes, and scoring notes JSON columns.

### Candidate metadata

Selected Scanner candidates expose:

- identity and rank snapshot: `symbol`, `name`, `rank`, `score`, `raw_score`,
  `final_score`, `quality_hint`;
- explanation text: `reason_summary`, `reasons`, `risk_notes`,
  `watch_context`;
- structured context: `key_metrics`, `feature_signals`, `boards`,
  `appeared_in_recent_runs`, `last_trade_date`, `scan_timestamp`;
- optional AI interpretation as public payload;
- realized outcome/review metadata;
- raw-ish but schema-locked diagnostics;
- consumer-safe diagnostics;
- candidate evidence/readiness/research summary/source provenance frames.

Evidence:

- `api/v1/schemas/scanner.py:326` defines `ScannerCandidateResponse`.
- `api/v1/schemas/scanner.py:204` defines source-confidence metadata.
- `api/v1/schemas/scanner.py:227` defines score explainability metadata.
- `api/v1/schemas/scanner.py:261` defines evidence packet metadata.
- `api/v1/schemas/scanner.py:286` defines consumer diagnostics.
- `src/storage.py:1704` persists candidate reason, metrics, risks, watch
  context, boards, and diagnostics JSON.
- `src/services/market_scanner_service.py:7271` replays persisted candidates
  into public candidate payloads and rebuilds consumer diagnostics and research
  frames.
- `src/services/market_scanner_service.py:7339` attaches consumer diagnostics
  and candidate evidence/research summary/provenance frames for live public
  candidate payloads.

### Score and source metadata

Scanner score explainability includes raw/final score, score delta/cap,
confidence, coverage, cap/degradation reasons, missing evidence, reason codes,
score-grade allowance, and nested source-confidence metadata. Source confidence
separately carries source labels, source type, as-of/freshness, fallback/stale/
partial/synthetic/unavailable flags, coverage, confidence weight, authority
flags, score-contribution flags, observation-only flags, and proxy-only flags.

Evidence:

- `src/services/market_scanner_service.py:6895` builds the source-confidence
  contract.
- `src/services/market_scanner_service.py:6911` sets score-grade/source
  authority flags.
- `src/services/market_scanner_service.py:6922` writes raw/final/public score
  values into the candidate payload.
- `src/services/market_scanner_service.py:6925` stores
  `score_explainability` in diagnostics.

## 2. Current add-to-Watchlist flow

The current frontend add flow sends only:

- `symbol`
- `market`
- `name`
- `source`
- `scannerRunId`
- `scannerRank`
- `scannerScore`
- `themeId`
- `universeType`
- `notes`

Evidence:

- `apps/dsa-web/src/pages/UserScannerPage.tsx:2516` adds a single candidate.
- `apps/dsa-web/src/pages/UserScannerPage.tsx:2582` adds batch candidates.
- `apps/dsa-web/src/api/watchlist.ts:129` serializes the create request.
- `api/v1/schemas/watchlist.py:20` defines the backend create schema.
- `api/v1/endpoints/watchlist.py:177` passes those fields into
  `WatchlistService.add_item()`.
- `src/services/watchlist_service.py:614` writes those fields into
  `UserWatchlistItem`.
- `src/storage.py:2061` defines the Watchlist item table.

The only free-text research carryover on create is `notes`, currently built
from key reason, risk summary, and public AI watch-plan text.

Evidence:

- `apps/dsa-web/src/pages/UserScannerPage.tsx:242` builds Watchlist notes.

## 3. Lineage lost on add

The add path preserves:

- user owner through the Watchlist row;
- symbol and market;
- source = `scanner`;
- scanner run id;
- scanner rank and public score snapshot;
- theme id and universe type;
- a bounded free-text note.

The add path does not persist these Scanner fields directly into the Watchlist
row:

- run profile label, run timing, run status, watchlist date, trigger mode;
- Scanner candidate `raw_score`, `final_score`, quality hint, score confidence,
  score cap/degradation reason, score-grade allowance;
- candidate `reason_summary`, `reasons`, `risk_notes`, `watch_context`,
  `key_metrics`, `feature_signals`, `boards`;
- `diagnostics.score_explainability`, `diagnostics.evidence_packet`,
  `consumerDiagnostics`, `candidateEvidenceFrame`,
  `candidateResearchReadiness`, `candidateResearchSummaryFrame`, and
  `candidateSourceProvenanceFrame`;
- source-confidence and freshness fields;
- provider observation sidecars and admin reason codes;
- comparison-to-previous and review-summary context;
- whether the saved score was inherited at add time or refreshed later, beyond
  the current timestamp-based UI cue.

Some lineage can be recovered later only if the Watchlist row still points to a
persisted Scanner candidate by `scanner_run_id + symbol`. Watchlist list
projection already uses that read-time join to recover limited score disclosure,
source-confidence projection, investor-signal projection, and catalyst exposure
sidecars.

Evidence:

- `src/services/watchlist_service.py:384` finds Scanner candidates by
  `scanner_run_id + symbol`.
- `src/services/watchlist_service.py:411` reads the candidate
  `diagnostics_json`.
- `src/services/watchlist_service.py:414` projects score disclosure.
- `src/services/watchlist_service.py:415` projects investor-signal metadata.
- `src/services/watchlist_service.py:430` builds the Watchlist intelligence
  payload.

## 4. Degraded and observation-only states that must block score-grade claims

Score-grade claims must fail closed when any of these are present:

- source authority is not explicitly true;
- score contribution is not explicitly true;
- `observationOnly` is true;
- fallback, stale, partial, synthetic, unavailable, or unknown source state;
- missing source-confidence metadata;
- missing or ambiguous freshness metadata;
- missing evidence or warning flags;
- cap or degradation reason exists;
- data quality is `missing`, `insufficient`, `partial`, or stale-like;
- source freshness or authority is explicitly not implied by a Watchlist score
  refresh context;
- score status is blocked, insufficient, unavailable, failed, stale, partial,
  cached, or unknown.

Evidence:

- `src/services/scanner_evidence_packet.py:231` requires explicit source
  authority and score contribution and disallows observation-only for
  score-grade allowance.
- `src/services/scanner_evidence_packet.py:242` maps limited and degraded
  states to non-complete consumer status.
- `src/services/market_scanner_candidate_evidence.py:170` treats provider/source
  observation-only and missing authority as observation-only.
- `src/services/market_scanner_candidate_evidence.py:179` requires explicit
  source authority and score contribution before score-grade allowance.
- `apps/dsa-web/src/pages/WatchlistPage.tsx:276` treats fallback/proxy/
  observation-only/unavailable/synthetic authority tokens as limited trust.
- `apps/dsa-web/src/pages/WatchlistPage.tsx:309` maps blocked, stale, cached,
  limited, failed, and unknown states into conservative UI states.
- `tests/test_watchlist_api.py:431` asserts Watchlist scanner intelligence keeps
  `score_grade_allowed` false for cache-only diagnostic evidence.
- `apps/dsa-web/src/pages/__tests__/WatchlistPage.test.tsx:724` asserts score
  refresh copy does not imply source freshness or authority.
- `apps/dsa-web/src/pages/__tests__/WatchlistPage.test.tsx:844` asserts stale
  inherited scanner scores do not render as verified latest evidence.

## 5. Safest v1 frontend/backend seams

### Backend seam

The safest backend seam is the existing Watchlist read projection in
`WatchlistService._scanner_intelligence_context_by_item()`.

Why:

- it is read-time only for Watchlist list responses;
- it already joins through persisted Scanner rows;
- it can preserve lineage without changing Scanner ranking, provider runtime,
  cache, DB schema, migrations, or create payload shape;
- it already has bounded projection helpers for source-confidence, reason
  families, investor signal, and catalyst exposures;
- missing Scanner rows naturally fail closed to the existing Watchlist item
  snapshot.

Do not add a new ranking/scoring path, provider call, cache mutation, or DB
column for v1.

### Frontend seam

The safest frontend seam is the Watchlist row/detail rail, using existing
`WatchlistItem.intelligence.scanner` and consumer-safe copy functions.

Why:

- row state already uses conservative disclosure states;
- detail rail already has collapsed data notes and collapsed investor-signal
  disclosure;
- empty state already directs users to Scanner without trading-action framing;
- frontend tests already guard raw/source/internal leakage.

Evidence:

- `apps/dsa-web/src/pages/WatchlistPage.tsx:399` formats scanner status with
  blocked and limited states.
- `apps/dsa-web/src/pages/WatchlistPage.tsx:416` filters unsafe scanner reasons.
- `apps/dsa-web/src/pages/WatchlistPage.tsx:772` shows only a bounded
  post-add-refresh lineage cue.
- `apps/dsa-web/src/pages/WatchlistPage.tsx:2150` renders current state/risk/
  next-step cards in the detail rail.
- `apps/dsa-web/src/pages/WatchlistPage.tsx:2313` keeps data notes collapsed.
- `apps/dsa-web/src/pages/__tests__/WatchlistPage.test.tsx:1192` asserts
  persisted scanner observation fields stay collapsed and consumer-safe.
- `apps/dsa-web/src/pages/__tests__/WatchlistPage.test.tsx:1748` asserts the
  empty state avoids unsafe action wording.

## 6. Proposed v1 lineage contract

### Contract shape

Use an additive consumer-safe projection named conceptually as
`scannerLineageV1` inside Watchlist scanner intelligence. It should be derived
from existing Scanner rows, not written as a new Scanner score or ranking input.

Minimum consumer-safe fields:

- `contractVersion`: `scanner_watchlist_lineage_v1`
- `source`: `scanner`
- `scannerRunId`
- `symbol`
- `market`
- `rankAtScan`
- `scoreAtScan`
- `scoreSnapshotKind`: `saved_at_add` or `post_add_refresh`
- `runProfile`
- `runCompletedAt`
- `watchlistAddedAt`
- `themeId`
- `universeType`
- `researchReason`
- `researchNextStep`
- `dataState`: bounded to consumer-safe states such as `available`, `limited`,
  `observation_only`, `insufficient`, `updating`, or `unavailable`
- `freshnessLabel`: bounded consumer label, not raw provider freshness
- `noAdviceBoundary`: true
- `observationOnly`: true when authority is missing or degraded
- `scoreGradeAllowed`: false unless all score-grade gates are explicitly true

Fields that must stay admin-only or absent from consumer-default UI:

- raw provider id/class/endpoint/trace/cache/fallback details;
- raw source-authority and score-contribution flags;
- raw reason-code payloads before localization;
- raw diagnostics JSON;
- provider observation entries;
- raw prompt or raw AI/provider payloads;
- licensing/right-to-display assertions.

### Research reason generation

For v1, generate `researchReason` from existing consumer-safe sources in this
priority order:

1. `candidateResearchSummaryFrame.primaryResearchReason` if present and safe;
2. `consumerDiagnostics.userFacingLabels` plus `candidate.reason_summary`;
3. saved Watchlist `notes`;
4. a generic observation-only fallback.

The reason must say why the symbol is being researched, not what action to take.
It should prefer language such as:

- `研究观察`
- `观察区`
- `参考区间`
- `风险边界`
- `补充证据`
- `刷新后再看`
- `保持观察`

It must not introduce order, execution, sizing, or guaranteed-result language.

## 7. Make Scanner more useful without changing ranking math

Safe improvements that do not change ranking math:

- show a clearer handoff summary after saving: run id, profile, scan time,
  saved rank/score snapshot, and whether later refresh changed the score;
- add a Watchlist detail rail section for Scanner lineage using existing
  intelligence fields and read-time Scanner candidate projection;
- surface research-readiness and missing-evidence summaries from existing
  frames in consumer-safe wording;
- distinguish `saved at add` from `refreshed after add`;
- keep first-run and empty-state copy focused on adding observation candidates
  and reviewing evidence;
- add frontend/backend tests that prove degraded lineage never becomes
  score-grade or action-grade copy;
- document the Scanner-to-Watchlist handoff as a research workflow, not an
  execution workflow.

Unsafe or deferred:

- changing scores, caps, weights, thresholds, shortlist membership, sorting, or
  ranking;
- changing provider order, live-call paths, fallback behavior, cache semantics,
  freshness/live labels, or source authority;
- adding migrations or stored contract versions;
- adding raw source-confidence/provider badges to consumer UI;
- expanding prompts, AI routing, or recommendation semantics.

## 8. UI and product risks

Main risks:

1. Score snapshot risk: Watchlist rows can show a saved scanner score even when
   the source/freshness authority is limited. Existing status-context copy
   mitigates this and must remain.
2. Lineage ambiguity: after score refresh, users may not know whether a score
   came from the original Scanner run or a later refresh. Existing post-add cue
   is useful but narrow.
3. Notes overloading: current free-text notes can carry useful context, but they
   are not a stable lineage contract and can blur evidence with commentary.
4. Raw metadata leakage: source-confidence and provider diagnostics are useful
   for maintainers but unsafe as consumer badges.
5. Action wording drift: helper names and older data labels may still originate
   from execution-style concepts, even though UI copy maps them to observation
   language. Future work must preserve the safe labels.
6. Empty-state overclaim: first-run and empty Watchlist states must remain
   "add observation candidates / collect evidence", not "ready to act".

## 9. First safe execution task

Recommended first task:

**T-1215-M1: Add Watchlist Scanner lineage read projection and consumer copy**

Goal:

- Add a read-only `scannerLineageV1`-style projection to Watchlist scanner
  intelligence from existing `scanner_run_id + symbol` joins.
- Render one compact lineage block in the Watchlist detail rail using
  consumer-safe fields only.
- Preserve existing Watchlist create payload and Scanner ranking/scoring.

Allowed files:

- `src/services/watchlist_service.py`
- `api/v1/schemas/watchlist.py`
- `apps/dsa-web/src/types/watchlist.ts`
- `apps/dsa-web/src/api/watchlist.ts` only if normalization needs a bounded
  safe projection guard
- `apps/dsa-web/src/pages/WatchlistPage.tsx`
- `tests/test_watchlist_api.py`
- `tests/test_watchlist_score_refresh.py`
- `apps/dsa-web/src/pages/__tests__/WatchlistPage.test.tsx`
- optional docs update in `docs/scanner/README.md` or
  `docs/frontend/WOLFYSTOCK_CONSUMER_DATA_QUALITY_UX.md`

Forbidden files/domains:

- no `src/services/market_scanner_service.py` ranking/scoring changes;
- no scanner score, score cap, threshold, shortlist, ranking, sorting, or
  selection changes;
- no provider runtime, provider order, live-call, fallback, cache, MarketCache,
  freshness/live-labeling, or source-authority changes;
- no DB model column additions, migrations, stored contract version changes, or
  source-of-truth changes;
- no package/config/lockfile changes;
- no AI prompt/model/routing/recommendation changes;
- no portfolio/options/backtest/accounting changes;
- no raw provider/source/admin diagnostics in consumer-default UI.

Suggested validation for that future task:

```bash
python -m pytest -q tests/test_watchlist_api.py tests/test_watchlist_score_refresh.py
npm --prefix apps/dsa-web run test -- src/pages/__tests__/WatchlistPage.test.tsx --run
git diff --check
./scripts/release_secret_scan.sh
```

Escalate before implementation if the task requires schema migration, Scanner
score/rank/order changes, provider/cache/runtime changes, or source-authority
semantics.

## 10. Audit validation plan

Required validation for this audit artifact:

```bash
git diff --check
./scripts/release_secret_scan.sh
```

Expected final diff:

- only `docs/codex/audits/T-1215-scanner-watchlist-pipeline-audit.md`

No backend/frontend tests are required for this report-only audit because no
runtime source or UI behavior was changed.

## Final audit decision

Proceed with T-1215-M1 as a bounded Watchlist read-projection and consumer-copy
task only after review. Do not change Scanner ranking/scoring math, provider
runtime, cache/fallback semantics, DB schema, migrations, or execution/advice
framing.
