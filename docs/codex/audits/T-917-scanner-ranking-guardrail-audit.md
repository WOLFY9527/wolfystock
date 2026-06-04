# T-917 Scanner Ranking Guardrail Audit

Task ID: T-917
Mode: READ-ONLY-AUDIT with explicit docs-only artifact and local commit authorization
Scope: implementation guardrail for future scanner ranking/scoring work. No runtime code was changed.

## Executive Verdict

Scanner ranking is a protected deterministic contract. Current shortlist
membership is produced by profile-specific universe filters, local/quote history
availability, score component weights, confidence caps, then a final stable sort
by `score` descending and `symbol` ascending. T-916-style candidate evidence,
T-915-style top-down context, readiness strips, and missing-evidence labels may
be added only as explanation/projection layers unless a future task explicitly
authorizes ranking changes.

The safe next implementation posture is:

1. Keep `shortlist`, `selected`, persisted `MarketScannerCandidate.rank`, and
   persisted `score` as the source of truth.
2. Add evidence only from already-collected diagnostics, evidence packets,
   source-confidence metadata, and scanner context frames.
3. Require golden before/after fixtures, rank-drift reports, and provider-call
   sentinels before any task touches score weights, filters, caps, or selection.

## Current Code Path Inventory

### Backend Entry And Profile Resolution

- API run requests accept `market`, `profile`, `shortlist_size`,
  `universe_limit`, `detail_limit`, `universe_type`, `theme_id`, and `symbols`
  (`api/v1/schemas/scanner.py:11`, `api/v1/endpoints/scanner.py:134`).
- Static market profiles define default shortlist/detail/universe limits,
  history depth, minimum price, liquidity, volume, turnover, and benchmark
  settings (`src/core/scanner_profile.py:10`, `src/core/scanner_profile.py:39`,
  `src/core/scanner_profile.py:60`, `src/core/scanner_profile.py:84`).
- `MarketScannerService.run_scan()` resolves profile, ownership, limits, and
  `default/theme/symbols` universe selection before dispatching to CN, US, or HK
  flows (`src/services/market_scanner_service.py:771`).

### CN Ranking Path

- CN resolves stock universe and realtime snapshot, restricts by theme/custom
  symbols when requested, and fails closed when snapshot or universe is missing
  (`src/services/market_scanner_service.py:835`,
  `src/services/market_scanner_service.py:884`,
  `src/services/market_scanner_service.py:903`).
- CN universe filtering removes non-A-share rows, missing names, ST names,
  low-price rows, suspended/zero-volume rows, low amount, low turnover unless
  degraded, and low volume ratio; then it keeps the highest amount/turnover
  rows within `universe_limit` (`src/services/market_scanner_service.py:5864`).
- CN pre-rank is computed from amount liquidity, turnover, volume ratio,
  60-day trend context, and range quality, then sorted by pre-rank, amount,
  60-day change, and turnover (`src/services/market_scanner_service.py:5966`).
- CN detail candidates are built from history plus snapshot fields, with
  history source, snapshot source, trend/momentum/liquidity/risk features, and
  empty component slots (`src/services/market_scanner_service.py:6258`).
- CN base score components are `pre_rank`, `trend`, `momentum`, `breakout`,
  `liquidity`, `activity`, `volatility_quality`, `relative_strength`,
  `sector_bonus`, and `penalties` (`src/services/market_scanner_service.py:6373`,
  `src/services/market_scanner_service.py:6635`).
- CN board/sector context can add only the existing bounded `sector_bonus`; this
  is already rank-affecting and must not be widened inside evidence/readiness
  tasks (`src/services/market_scanner_service.py:6592`,
  `src/services/market_scanner_service.py:6611`).

### US/HK Ranking Path

- US/HK share `_run_quote_market_scan()`: resolve bounded universe, build a
  local-first filtered universe, compute pre-rank, optionally load quote/gap
  context, build candidates, apply scores, finalize candidates, then prepare the
  shortlist (`src/services/market_scanner_service.py:1920`).
- US filters unsupported symbols, benchmark symbol, insufficient history,
  low price, low 20-day average amount, and low 20-day average volume before
  sorting by average amount, 20-day return, and 60-day return
  (`src/services/market_scanner_service.py:2641`).
- US pre-rank uses amount liquidity, volume, 60-day trend, 20-day momentum,
  range quality, and benchmark-relative behavior
  (`src/services/market_scanner_service.py:2866`).
- Optional US quote context supplies live price, day change, volume/amount,
  prior close, and gap percent; missing quote falls back to history-only
  candidate fields (`src/services/market_scanner_service.py:2936`,
  `src/services/market_scanner_service.py:2983`).
- US final components are `pre_rank`, `trend`, `momentum`, `liquidity`,
  `activity`, `volatility_quality`, `relative_strength`,
  `benchmark_relative`, `gap_context`, and `penalties`
  (`src/services/market_scanner_service.py:6450`,
  `src/services/market_scanner_service.py:6667`).
- HK follows the same quote-market shape with HK-specific universe, benchmark,
  liquidity, gap, and penalty constants (`src/services/market_scanner_service.py:2171`,
  `src/services/market_scanner_service.py:2289`,
  `src/services/market_scanner_service.py:2430`,
  `src/services/market_scanner_service.py:6521`).

### Score Caps, Diagnostics, And Final Sort

- Score caps are not cosmetic: `_apply_score_caps_and_explainability()` writes
  `raw_score`, `final_score`, and replaces `candidate["score"]` with the capped
  final score. Fallback, stale, partial, proxy, and missing evidence therefore
  can affect rank today and must remain protected
  (`src/services/market_scanner_service.py:6810`).
- The final shortlist sort is deterministic: sorted candidates use
  `(-score, symbol)`, then the top `resolved_shortlist_size` rows receive ranks
  starting at 1 (`src/services/market_scanner_service.py:1120`).
- AI interpretation is attached after shortlist selection and is bounded by a
  system prompt that says deterministic score/rank remains the primary order;
  non-CN profiles skip AI interpretation (`src/services/scanner_ai_service.py:21`,
  `src/services/scanner_ai_service.py:63`,
  `src/services/scanner_ai_service.py:111`).
- Run diagnostics include coverage, provider attribution, scanner data,
  universe selection, candidate diagnostics, and context metadata; these should
  explain the run, not recompute rank (`src/services/market_scanner_service.py:1000`,
  `src/services/market_scanner_service.py:2034`).

### Persistence And Readback

- Completed runs persist a `MarketScannerRun` plus only shortlisted
  `MarketScannerCandidate` rows with persisted `rank`, `score`, reasons,
  feature signals, risk notes, watch context, boards, and diagnostics
  (`src/services/market_scanner_service.py:1779`,
  `src/storage.py:1591`,
  `src/storage.py:1626`).
- Fresh responses return `selected` and `shortlist` from the same persisted
  shortlist order, with `scannerContextFrame` built from diagnostics only after
  shortlist preparation (`src/services/market_scanner_service.py:1869`).
- Persisted detail reads fetch candidates ordered by `rank asc, id asc`, rebuild
  `shortlist` from saved rows, and rebuild `scannerContextFrame` from saved
  diagnostics (`src/repositories/scanner_repo.py:191`,
  `src/services/market_scanner_service.py:4620`).
- History `top_symbols` uses persisted `summary_json.shortlisted_codes` or the
  first saved candidate rows; future ranking work must preserve this readback
  contract (`src/services/market_scanner_service.py:5101`).

### Frontend Consumption

- Web types expose `rank`, `score`, `rawScore`, `finalScore`, diagnostics,
  consumer diagnostics, `selected`, `candidates`, `shortlist`, and
  `scannerContextFrame` without recomputing backend rank
  (`apps/dsa-web/src/types/scanner.ts:196`,
  `apps/dsa-web/src/types/scanner.ts:352`,
  `apps/dsa-web/src/types/scanner.ts:382`).
- `buildScannerTopDownContextView()` reads only `runDetail.scannerContextFrame`
  plus the existing universe fallback; it produces chips and summary text, not
  rank inputs (`apps/dsa-web/src/api/researchReadiness.ts:602`,
  `apps/dsa-web/src/api/researchReadiness.ts:639`).
- `UserScannerPage` has local display sort/filter controls. These can reorder
  visible rows by user choice, but they are UI state only and must not be
  confused with backend ranking semantics
  (`apps/dsa-web/src/pages/UserScannerPage.tsx:2005`,
  `apps/dsa-web/src/pages/UserScannerPage.tsx:2034`,
  `apps/dsa-web/src/pages/UserScannerPage.tsx:2098`,
  `apps/dsa-web/src/pages/UserScannerPage.tsx:3030`).
- The readiness strip and top-down context strip render above the status strip
  and table; they must remain additive context surfaces
  (`apps/dsa-web/src/pages/UserScannerPage.tsx:2770`).

## Score Inputs And Non-Inputs

### Rank-Affecting Inputs Today

- Profile thresholds and limits: shortlist size, universe limit, detail limit,
  history days, minimum bars, price, liquidity, turnover, volume, benchmark.
- Universe selection: default market universe, manually maintained theme seeds,
  or custom symbols. Theme currently affects membership by input set, not by a
  hidden theme score.
- CN technical/liquidity/history inputs: snapshot price/change/amount/volume,
  turnover, volume ratio, amplitude, 60-day change, local/remote history bars,
  moving averages, 5/20-day returns, 20-day high distance, ATR/range, relative
  strength, board/sector bonus, and penalties.
- US/HK technical/liquidity/history/gap inputs: local-first history, price,
  average amount/volume, 5/20/60-day returns, moving averages, ATR/range,
  benchmark-relative return, optional quote availability, optional gap percent,
  and penalties.
- Confidence caps: fallback, stale, partial, proxy, missing core evidence, and
  source-confidence fields are rank-affecting because they set final score.

### Not Rank-Affecting Today

- `scannerContextFrame.marketReadiness`, `macroRegime`, `liquidityFrame`,
  `assetClassBias`, `themeFrame`, `universePolicy`, and `noAdviceBoundary`.
- Market Overview / Market Temperature `marketRegimeSynthesis`, Liquidity
  Monitor `capitalFlowSignal` or `liquidityImpulseSynthesis`, and Rotation Radar
  `rotationFamilyRollup` or `themeFlowSignal` when they are consumed through
  scanner context projections.
- Candidate evidence packets, factor observations, consumer diagnostics,
  readiness strips, score trust strips, and missing-evidence labels.
- AI interpretation and AI-generated theme explanations. AI-generated themes
  may create a seed universe, but the generated evidence must not become a score
  component without protected-domain approval.
- Frontend local sort/filter controls. These change display order only.

## Protected Invariants

1. Shortlist order stability: for the same fixtures and collected inputs,
   `shortlist` and `selected` must keep the same symbols, same ranks, same
   final scores, and same `(-score, symbol)` tie-break behavior.
2. Selected candidates: `selected` must continue to equal `shortlist` for
   current scanner detail responses unless a future contract explicitly changes
   selection semantics.
3. Score scale: public `score`, `raw_score/rawScore`, and
   `final_score/finalScore` remain 0-100 bounded values. Any cap change is a
   ranking change.
4. Filter semantics: profile thresholds, market-specific universe filtering,
   `detail_limit >= shortlist_size`, theme/custom-symbol restrictions,
   unsupported-market skips, benchmark-symbol skips, and data-failed/rejected
   statuses must not drift in readiness/UI tasks.
5. Candidate diagnostics: `candidates[]` must remain diagnostic evidence, not a
   hidden alternative ranking list. Status and failed-rule vocabulary must stay
   bounded and consumer-safe.
6. Persisted run history: saved `MarketScannerCandidate.rank/score`,
   `summary_json.shortlisted_codes`, `top_symbols`, watchlist comparison rank
   deltas, and readback order must not be recomputed or rewritten by evidence
   projections.
7. CN fail-closed behavior: missing universe/snapshot stays blocked; degraded
   local-history mode stays lower-confidence/observe-only; public/proxy CN
   sources must not be promoted to score-grade authority in normal scanner
   readiness work.
8. No-advice boundary: Scanner output remains a research/observation list, not
   an automated execution instruction. Future copy/tests must preserve
   `noAdviceBoundary` and `consumerActionBoundary=no_advice` semantics.
9. Provider/cache boundary: no hidden provider fanout, provider-order change,
   cache TTL/SWR change, source-authority promotion, or live-labeling change may
   enter a ranking guard/evidence task.

## Safe Evidence Additions

The following are safe only when implemented as additive projections with
non-mutation tests:

- Run readiness projection: adapt existing diagnostics into
  `build_research_readiness_v1()`; do not create a parallel verdict engine.
- Candidate evidence/readiness: derive from existing `score_explainability`,
  `source_confidence`, `evidence_packet`, factor observations, provider
  observation metadata, and bounded candidate diagnostics. Do not fetch new data
  to make rejected or missing rows look complete.
- Missing evidence labels: show missing fundamentals, news, catalysts,
  earnings, valuation, source authority, freshness, sector/theme, or quote
  context as labels or next-evidence text only. Missing labels must not become
  score penalties unless a ranking task explicitly authorizes the formula.
- Explanation-only context: Market Overview, Liquidity, and Rotation context can
  appear in `scannerContextFrame`, compact strips, or candidate detail chips when
  they preserve observation-only/source-authority flags and fail closed on
  missing metadata.
- UI surfacing: compact strips/chips/bounded disclosures are acceptable when
  they consume existing fields and tests prove visible rank/score/order did not
  change.

## Approval Gate For Future Ranking Changes

Any future task that changes scoring, ranking, sorting, thresholds, filters,
candidate membership, score caps, provider authority, or provider fanout must
meet this gate before implementation:

1. Explicit protected-domain task: the prompt must name scanner ranking/scoring
   as allowed and list exact files allowed to change.
2. Before/after fixtures: include deterministic CN, US, and HK fixtures covering
   complete data, missing quote, fallback/proxy source, partial history, theme
   universe, custom-symbol universe, and CN blocked/degraded cases.
3. Benchmark snapshots: persist expected input universe counts, exclusion
   counts, evaluated counts, component scores, raw/final scores, cap reasons,
   ranks, shortlisted symbols, and readback `top_symbols`.
4. Rank-drift report: every changed fixture must report old/new order, old/new
   score, selected additions/removals, reason for drift, and whether drift is
   intentional.
5. Provider fanout proof: fake providers or route collectors must prove no new
   broad scanner-wide calls, no new live provider path, no source-authority
   promotion, and no cache write/TTL/SWR behavior change unless explicitly
   approved.
6. Public-safety proof: no direct execution wording, no raw provider payloads,
   no stack traces, no credentials, no route/cache internals, and
   `noAdviceBoundary` remains visible where applicable.
7. Persistence proof: save-run/read-detail/list-history/watchlist-comparison
   assertions must prove persisted rank/score/history semantics match the
   approved before/after snapshot.
8. Documentation update: any approved ranking change must update
   `docs/market-scanner.md`, the relevant audit/architecture note, and
   `docs/CHANGELOG.md` because it changes user-visible scanner interpretation.

## Focused Tests For T-917R

Recommended future execution task: add tests only, without changing runtime
ranking behavior.

- Backend golden order tests:
  - Freeze CN fake-data shortlist signature: symbols, ranks, scores,
    `raw_score`, `final_score`, component keys, and cap reasons.
  - Freeze US theme shortlist signature using `crypto_miners` fixtures,
    including rejected/data-failed counts and quote-call count.
  - Add HK fixture if existing local fake coverage can do so without provider
    calls.
- Non-mutation adapter tests:
  - Run the same fixture with no context, supportive context, fallback/proxy
    context, and CN blocked/degraded readiness. Assert identical shortlist
    symbols, ranks, final scores, selected count, and persisted readback.
  - Add candidate evidence/readiness payloads from existing diagnostics and
    assert identical rank/score/shortlist.
- Provider fanout sentinel:
  - Fake data managers should count stock-list, snapshot, history, quote, board,
    market-cache, liquidity, and rotation reads before/after additive evidence.
    Evidence-only paths must not add scanner-wide provider calls.
- Persistence/history tests:
  - Save a run, call `get_run_detail()`, `list_runs()`, and recent watchlist
    readback. Assert `top_symbols`, `comparison_to_previous`, persisted ranks,
    and scores match the baseline.
- Frontend tests:
  - Default rendered order mirrors server rank before the user touches local
    sort controls.
  - `scannerContextFrame` and candidate evidence chips do not mutate visible
    `NVDA -> AVGO -> AMD`-style order or scores.
  - Candidate filter/sort controls remain UI-only and never write back rank,
    score, or selection semantics.
  - CN blocked/unavailable context shows consumer-safe labels without internal
    terms or execution wording.

Existing nearby coverage already includes basic sorted shortlist persistence,
scanner context fail-closed/supportive/readiness tests, additive API schema
compatibility, candidate diagnostics, public-safety assertions, and frontend
top-down context non-mutation checks (`tests/test_market_scanner_service.py:900`,
`tests/test_market_scanner_service.py:930`,
`tests/test_market_scanner_service.py:1075`,
`tests/api/test_scanner.py:16`,
`tests/api/test_scanner_diagnostics.py:10`,
`tests/test_market_scanner_public_safety.py:85`,
`apps/dsa-web/src/pages/__tests__/UserScannerPage.test.tsx:1046`).

## High-Risk Files And Domains

These must stay out of normal UI/readiness/evidence tasks unless the task
explicitly grants scanner ranking or protected-domain scope:

- `src/services/market_scanner_service.py`: ranking, filters, score components,
  confidence caps, shortlist sorting, run finalization, readback payloads, CN
  fail-closed readiness, and provider diagnostics.
- `src/core/scanner_profile.py`: profile thresholds, limits, benchmark defaults,
  and market profile routing.
- `src/core/scanner_theme_registry.py`: seed universe membership and
  AI-generated theme registration semantics.
- `src/repositories/scanner_repo.py` and `src/storage.py`: persisted run and
  candidate rank/score/history authority.
- `api/v1/schemas/scanner.py` and `api/v1/endpoints/scanner.py`: public
  request/response contract and endpoint behavior.
- `src/services/market_scanner_context_adapter.py`: MarketCache, Liquidity, and
  Rotation context reads. Projection-only work may use it, but normal UI tasks
  must not expand cache/provider behavior here.
- `src/services/scanner_evidence_packet.py` and
  `src/services/scanner_factor_observations.py`: safe as projections, unsafe if
  reused as hidden score inputs.
- `src/services/provider_capability_matrix.py`, `data_provider/**`,
  `src/services/market_cache.py`, Market Overview, Liquidity Monitor, and
  Rotation Radar services: provider order, source authority, freshness,
  fallback, cache, and cross-surface score semantics.
- `src/services/scanner_ai_service.py`: AI prompt/routing/output boundaries.
  AI must remain secondary explanation, not first-round selection or ranking.
- `apps/dsa-web/src/pages/UserScannerPage.tsx`,
  `apps/dsa-web/src/api/researchReadiness.ts`,
  `apps/dsa-web/src/types/scanner.ts`, and scanner presenter/score-trust
  components: UI display, local sort/filter, readiness strips, and evidence
  labels must not write or imply backend rank/score changes.
- Config, lockfiles, CI, migrations, auth/RBAC, accounting/portfolio,
  broker/execution workflows, backtest calculations, notification routing, and
  provider credentials are outside normal scanner readiness/evidence tasks.

## Implementation Recommendation

Proceed with T-917R as a tests-only guardrail task if ranking protection needs
code enforcement. The first useful slice is not a ranking rewrite; it is a
baseline fixture suite that freezes current CN/US/HK order, scores, caps,
selection, readback, and provider-call counts before any future protected-domain
ranking work is considered.
