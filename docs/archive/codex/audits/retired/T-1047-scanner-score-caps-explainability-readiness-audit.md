# T-1047 Scanner score caps explainability readiness audit

Task ID: T-1047-AUDIT

Task title: Scanner score caps explainability readiness audit

Mode: READ-ONLY-AUDIT with one explicitly allowed docs-only audit artifact.

Allowed artifact:
`docs/codex/audits/T-1047-scanner-score-caps-explainability-readiness-audit.md`

Observed workspace:

- cwd:
  `/Users/yehengli/worktrees/t1047-scanner-score-caps-explainability-audit`
- branch: `codex/t1047-scanner-score-caps-explainability-audit`
- local branch divergence from `origin/main` at pre-write check: `0 0`

Scope boundary:

- Source, tests, config, package, lockfile, API, frontend, provider, cache,
  runtime, scoring, ranking, filtering, and persistence files were inspected
  only.
- This audit does not implement score-cap, explainability, API, or UI changes.
- Scanner score math, score caps, shortlist membership, candidate ordering,
  provider/cache/runtime fallback behavior, and persisted result semantics are
  protected domains.

## Readiness verdict

The scanner already applies source-confidence score caps before shortlist
ordering. A future task must treat score caps as live protected scoring and
ranking behavior, not as a display-only annotation.

The system is not ready for a small or opportunistic score-cap semantics change.
Changing cap weights, cap reasons, fallback penalties, ranking thresholds,
filters, tie-break behavior, provider fallback, or upstream degraded-data
defaults would directly risk score/order drift.

The smallest safe future write is one additive explainability metadata lock:
make existing score-cap/source-confidence/evidence provenance metadata explicit
and contract-tested across backend DTOs, API serialization, frontend shared
types, and UI adapter paths, without changing `raw_score`, `final_score`,
`score`, shortlist selection, sorting, provider calls, cache behavior, or
fallback semantics.

Recommended future write count: exactly one.

Recommended future write:

- Explainability metadata lock for existing scanner score-cap evidence.

Not recommended:

- Any immediate score-cap calculation, cap-weight, ranking, filtering, provider,
  fallback, cache, or runtime behavior change.

## Audit questions and answers

### 1. Where are scores, caps, ranks, and shortlist order computed?

Primary scanner scoring and ordering lives in
`src/services/market_scanner_service.py`.

- Market/profile limits and thresholds are defined in
  `src/core/scanner_profile.py:10`, `:39`, `:60`, and `:84`.
- CN scan flow resolves universe/filtering, pre-rank, detail candidates,
  component scoring, score caps, then shortlist ordering
  (`src/services/market_scanner_service.py:793`, `:938`, `:987`, `:999`).
- US/HK share the quote-market scan path with local history, optional quote
  context, market-specific scoring, score caps, and shortlist preparation
  (`src/services/market_scanner_service.py:1936`, `:2029`, `:2041`, `:2045`).
- Score caps are applied in `_apply_score_caps_and_explainability()`, which
  writes `raw_score`, `final_score`, `diagnostics["score_explainability"]`, and
  replaces `candidate["score"]` with the capped final score
  (`src/services/market_scanner_service.py:6835`, `:6916`).
- Source confidence weights/caps are computed in
  `src/services/source_confidence_contract.py:453` and `:810`.
- Final shortlist ordering sorts by `score` descending and `symbol` ascending
  before assigning ranks (`src/services/market_scanner_service.py:1133`).
- Persisted readback fetches candidates by `rank asc`
  (`src/repositories/scanner_repo.py:191`).

Conclusion: score caps are already rank-affecting because they change the
stored candidate `score` before final shortlist sorting.

### 2. Where is evidence/source quality available, and where is it lost?

Rich evidence exists around shortlisted candidates, but it is not uniformly
locked as a first-class end-to-end contract.

Available metadata:

- Candidate-level source and data-quality inputs exist before final scoring,
  including `history/source/rows/stale`, `quote_context/source/trace/available`,
  `snapshot_source`, and `degraded_mode_used`
  (`src/services/market_scanner_service.py:965`, `:1181`, `:3066`, `:6370`).
- CN candidates also carry `cn_provider_observation` sidecar metadata before
  scoring (`src/services/market_scanner_service.py:981`, `:1638`).
- Shortlisted candidates retain `raw_score`, `final_score`,
  `score_explainability`, `evidence_packet`, `consumerDiagnostics`, and source
  provenance style frames (`src/services/market_scanner_service.py:7310`,
  `:7391`).
- API candidate DTOs expose score fields, diagnostics, consumer diagnostics,
  candidate evidence/readiness/summary/source-provenance frames, and run-level
  scanner context (`api/v1/schemas/scanner.py:204`, `:225`, `:239`).
- `evidence_packet` includes freshness/data-quality/user-facing labels,
  warning flags, provider observation, and evidence buckets
  (`src/services/scanner_evidence_packet.py:311`, `:368`).

Loss and looseness boundaries:

- Non-shortlist candidates degrade to bounded diagnostics rather than retaining
  the same rich explainability payload
  (`api/v1/schemas/scanner.py:251`,
  `tests/api/test_scanner_diagnostics.py:42`).
- Persistence stores shortlisted rows; `score` is first-class, while raw/final
  score and explainability detail depend on diagnostics JSON replay
  (`src/storage.py:1626`,
  `src/services/market_scanner_service.py:7271`).
- API schemas still use broad `Dict[str, Any]` for several important evidence
  and provenance payloads (`api/v1/schemas/scanner.py:204`, `:239`, `:251`).
- Frontend shared `ScannerCandidate` types do not elevate every existing
  backend candidate evidence/provenance frame as a first-class field
  (`apps/dsa-web/src/types/scanner.ts:352`).
- `diagnosticToCandidate()` fallback conversion clears diagnostics, which can
  erase candidate-level evidence/source-quality detail on that UI path
  (`apps/dsa-web/src/pages/UserScannerPage.tsx:1305`).

Conclusion: shortlist explainability is materially present, but the contract is
not tight enough to safely treat future score-cap work as explainability-only.

### 3. Can observe-only, fallback, stale, partial, or degraded states influence score/order?

Yes, but there are two distinct classes.

Observation-only sidecars that are currently guarded as non-scoring:

- CN provider observation and baostock observation sidecars are tested not to
  change rank or score (`tests/test_market_scanner_service.py:3392`, `:3490`,
  `:3818`).
- Factor/readiness observation sidecars are tested as projection-only and do
  not change rank or score (`tests/test_market_scanner_service.py:2357`,
  `:2409`; `tests/test_scanner_factor_observations.py:216`).
- AI interpretation and top-down context are attached after deterministic
  shortlist/rank production and should remain additive
  (`src/services/scanner_ai_service.py:24`, `:674`;
  `src/services/market_scanner_context_adapter.py:2`).

Fallback/stale/partial/source-confidence states that do affect score/order:

- `fallback`, `stale`, `partial`, `unavailable`, and `synthetic` confidence
  states cap final score through confidence weights such as `0.4`, `0.6`,
  `0.7`, `0.0`, and `0.2`
  (`src/services/source_confidence_contract.py:810`;
  `src/services/market_scanner_service.py:6916`).
- US/HK `quote_available=False`, `history_source=="local_partial_fallback"`,
  and CN partial local fallback can directly add penalties
  (`src/services/market_scanner_service.py:6446`, `:6526`, `:6597`).
- Missing US/HK quote context can implicitly affect component scores because
  price/change/amount/volume fall back to history-derived values and missing
  `gap_pct` follows default gap scoring paths
  (`src/services/market_scanner_service.py:3013`, `:6511`, `:6582`).
- CN degraded snapshot behavior can relax turnover filtering and fill missing
  turnover to the profile floor, affecting universe inclusion and pre-rank
  order (`src/services/market_scanner_service.py:5653`, `:5954`).

Conclusion: not every observation is harmless. Some degraded-source states are
already part of protected score math and ordering.

### 4. Can current API/UI explain strong evidence vs observation/degraded evidence?

Partially.

What works today:

- API responses include raw/final score, diagnostics, consumer diagnostics,
  candidate evidence/readiness/summary/source-provenance frames, and run-level
  scanner context (`api/v1/schemas/scanner.py:204`, `:225`, `:239`, `:265`).
- Frontend has typed models for `ScannerSourceConfidence`,
  `ScannerScoreExplainability`, `ScannerEvidencePacket`, and
  `ScannerConsumerDiagnostics`
  (`apps/dsa-web/src/types/scanner.ts:196`, `:215`, `:228`, `:288`).
- The scanner page renders research readiness, top-down context, candidate
  diagnostics, candidate evidence strips, and candidate research summary
  surfaces (`apps/dsa-web/src/pages/UserScannerPage.tsx:2747`, `:2850`;
  `apps/dsa-web/src/components/scanner/ScannerCandidateEvidenceStrip.tsx:160`;
  `apps/dsa-web/src/components/scanner/ScannerCandidateResearchSummary.tsx:224`).
- `toCamelCase()` deeply converts API payload shape and does not itself filter
  unknown fields (`apps/dsa-web/src/api/utils.ts:8`).

Remaining explainability risks:

- Default ranked-row trust display intentionally strips diagnostics/metadata
  before passing data into `ScannerScoreTrustStrip`, so the main consumer row
  does not necessarily show the raw cap/fallback/proxy/stale reason for every
  candidate (`apps/dsa-web/src/pages/UserScannerPage.tsx:358`, `:3302`).
- `ScannerScoreExplainability` does not model all backend-emitted fields such
  as `score_cap`, `score_delta`, and `missing_evidence`
  (`src/services/market_scanner_service.py:6925`;
  `apps/dsa-web/src/types/scanner.ts:215`).
- `ScannerEvidencePacket` and local candidate evidence/summary types do not
  model every existing backend evidence bucket and summary field
  (`apps/dsa-web/src/types/scanner.ts:228`;
  `src/services/market_scanner_candidate_evidence.py:68`;
  `src/services/market_scanner_candidate_summary.py:169`).
- Diagnostic fallback paths can lose diagnostics/source-quality payloads
  (`apps/dsa-web/src/pages/UserScannerPage.tsx:1305`).

Conclusion: current UI can present safe aggregate distinctions, but the
end-to-end type and adapter contract is still too loose for score-cap readiness
to be considered locked.

### 5. What tests currently guard this, and what gaps remain?

Existing backend/API tests provide a useful base:

- Score/raw/final/cap/source-confidence boundaries:
  `tests/test_market_scanner_service.py:1780`, `:1893`, `:2135`, `:2227`.
- Shortlist/evidence/readiness/factor observations do not change rank/score:
  `tests/test_market_scanner_service.py:2357`, `:2409`;
  `tests/test_scanner_factor_observations.py:216`.
- CN provider observation and baostock observation do not change rank/score:
  `tests/test_market_scanner_service.py:3392`, `:3490`, `:3818`.
- API/golden contracts preserve rank/raw/final/selected/shortlist behavior:
  `tests/test_scanner_golden_contracts.py:131`;
  `tests/test_market_scanner_api_contract.py:441`;
  `tests/api/test_scanner.py:194`.
- API contracts retain candidate evidence/readiness/summary/provenance and
  consumer diagnostics:
  `tests/test_market_scanner_api_contract.py:300`, `:365`, `:562`, `:703`,
  `:1194`.
- Evidence packet and source provenance sidecars have focused backend tests:
  `tests/test_scanner_evidence_packet.py:66`, `:171`;
  `tests/services/test_market_scanner_source_provenance_sidecar.py:193`,
  `:213`, `:323`.
- Frontend has API camelCase and scanner page rendering/safe-copy coverage:
  `apps/dsa-web/src/api/__tests__/scanner.test.ts:18`;
  `apps/dsa-web/src/pages/__tests__/UserScannerPage.test.tsx:1216`, `:1287`,
  `:1388`, `:1819`, `:1876`.

Known gaps:

- No dedicated tie-break test was found for same-score ordering even though
  code defines `(-score, symbol)`.
- Positive frontend coverage for `limitedByResultCap=true` was not found; the
  observed fixture path covers the false branch
  (`apps/dsa-web/src/pages/__tests__/UserScannerPage.test.tsx:280`;
  `apps/dsa-web/src/pages/UserScannerPage.tsx:867`).
- There is no single end-to-end metadata lock asserting that backend
  `score_explainability` fields survive API serialization, camelCase
  conversion, shared TS types, fallback adapters, and row/detail presentation
  without affecting rank/order.

Conclusion: tests protect important score/rank guardrails, but not the full
explainability metadata contract needed before any score-cap-facing UI or API
work.

## Protected-domain warnings for future tasks

Future writes must stop and request explicit protected-domain authorization if
they touch any of these areas:

- scanner scoring math, score components, cap weights, cap reason precedence,
  `raw_score`, `final_score`, or `score`;
- candidate ranking, shortlist membership, sorting, tie-breakers, selected rows,
  thresholds, filters, pre-rank, or result caps;
- provider adapters, provider priority, cache behavior, runtime fallback,
  timeout behavior, quote/history/snapshot normalization, or degraded-mode
  defaults;
- API behavior changes that alter payload semantics rather than only locking
  existing additive metadata;
- frontend logic that reorders rows, hides rows, changes score labels into
  recommendations, or turns observation/degraded states into advice;
- any change that makes observe-only, fallback, stale, partial, unavailable, or
  synthetic inputs alter ordering differently than they do today.

Especially important: upstream degraded defaults and relaxed filters are already
ranking-sensitive. They must not be framed as harmless explainability work.

## Single recommended future write

### Explainability metadata lock

Goal:

- Lock the existing scanner score-cap explainability metadata as an additive,
  consumer-safe contract.

Expected scope:

- Make existing backend `score_explainability`, source-confidence, evidence
  packet, and candidate provenance fields explicit enough in API/DTO contracts
  that unknown `Dict[str, Any]` and local frontend casts are no longer the main
  preservation mechanism.
- Align frontend shared types with existing backend fields such as `score_cap`,
  `score_delta`, `missing_evidence`, candidate evidence frames, candidate
  source provenance frames, and result-cap metadata.
- Preserve existing metadata through API adapters and diagnostic fallback paths.
- Add focused tests proving metadata survival across backend contract, API
  serialization, frontend API conversion, and scanner page adapter surfaces.

Forbidden in that future write unless separately authorized:

- no score-cap math changes;
- no confidence-weight changes;
- no rank/order/filter/shortlist/selected changes;
- no provider/cache/runtime/fallback behavior changes;
- no new provider calls;
- no persisted score semantics changes;
- no investment or trading advice copy.

Suggested validation for that future write:

- focused backend/API contract tests for score explainability metadata;
- focused frontend API/type/page adapter tests for metadata preservation;
- rank-drift guard comparing shortlist symbols/ranks/scores before and after;
- `git diff --check`;
- `./scripts/release_secret_scan.sh`.

## Why not change score caps now?

Changing score caps now would cross from explainability into protected scanner
behavior because:

- final score is already capped before sorting;
- degraded source-confidence states and fallback penalties can change rank
  today;
- upstream degraded-data defaults can affect component scores before cap;
- current DTO/UI contracts do not yet lock all explainability metadata needed to
  explain such changes safely;
- tests protect many guardrails but do not lock the full metadata path or
  same-score tie-break behavior.

Therefore the safe sequence is metadata lock first, then a separately
authorized scoring/ranking task only if product and engineering explicitly want
cap semantics to change.

## Risk zones

- Score/order drift from cap weight or penalty changes.
- Hidden drift from fallback numeric defaults or degraded filter relaxation.
- Metadata loss through opaque API dictionaries, frontend shared-type gaps, and
  diagnostic fallback conversion.
- Consumer row under-explanation because trust payloads can be stripped before
  default row display.
- Non-shortlist candidates lacking the same explainability detail as shortlist
  candidates.
- Test gaps around tie-break ordering and positive result-cap display.

## Final audit decision

The scanner has enough existing metadata to justify one narrow metadata-lock
write, but not enough end-to-end contract hardening to justify score-cap
semantics changes under an explainability/readiness task.

Decision:

- proceed only with a future explainability metadata lock;
- defer score-cap calculation or ranking changes to a separate protected-domain
  task with explicit authorization, rank-drift evidence, and broader
  verification.
