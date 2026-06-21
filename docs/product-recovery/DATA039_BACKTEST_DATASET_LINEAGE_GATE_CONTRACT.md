# DATA-039 Backtest Dataset Lineage Gate Contract

Task ID: DATA-039

Status: docs-only gate contract. This document does not implement runtime code,
schemas, API routes, provider behavior, cache behavior, backtest engine changes,
portfolio allocation, factor panel generation, or frontend behavior.

## 1. Executive conclusion

WolfyStock backtest results are not professional-grade without dataset lineage
because performance metrics cannot be trusted when the dataset itself cannot be
identified, reproduced, and audited. A return series is only meaningful when the
consumer can verify which symbols were eligible, which bars were used, how those
bars were adjusted, which sessions were included or excluded, whether inactive
members were present, and whether the same historical snapshot can be reopened.

DATA-031 correctly found the current system research-useful: deterministic
single-symbol rule backtests, stored readback, local-only universe jobs,
support exports, and diagnostic readiness surfaces are useful for research and
debugging. They are not enough for professional backtesting because the current
contracts still expose incomplete adjusted-data, corporate-action, calendar,
point-in-time universe, survivorship, source-authority, and reproducibility
evidence (`docs/product-recovery/DATA031_BACKTEST_PROFESSIONAL_UPGRADE_AUDIT.md`,
`src/services/backtest_professional_readiness.py`,
`src/services/backtest_data_provenance_projection.py`).

This gate enables future rule backtests, parameter sweeps, factor tests, and
portfolio backtests to state exactly why a result is usable, limited, diagnostic,
or blocked before the result is trusted. It creates a shared acceptance contract
for dataset lineage, execution lineage, and stored readback evidence.

This task does not implement the gate in application code. It does not add API
fields, rewrite stored runs, change engine math, select providers, create
adjusted bars, build point-in-time universes, run parameter sweeps, build factor
panels, or run portfolio allocation backtests.

## 2. Current backtest data assumptions

### Local bars

Current deterministic rule backtests run over available bars. Single-symbol
execution can use stored daily bars and the local US history path, and universe
jobs explicitly read local `StockDaily` rows. Local availability is a useful
research guard, but local availability is not a dataset contract. It does not by
itself prove bar source authority, adjustment method, missing-bar policy, PIT
membership, stale handling, or reproducibility hash.

### Close signal / next open fill

The current default rule engine evaluates ordinary rule signals on bar close and
executes the pending entry or exit on the next bar open. If the required open is
missing, the engine can fall back to close. If a position remains open at the
end of the window, the current v1 model force-flattens at the terminal bar close
fallback. This timing is deterministic and explainable, but it is not a
professional execution simulator.

### Fee/slippage bps

Current cost handling is bounded per-side `fee_bps` and `slippage_bps`. It is a
simple assumption model, not a spread, impact, partial-fill, venue, queue,
halt/limit, tax, stamp-duty, or broker-grade fill model. The dataset-lineage
gate must therefore record execution lineage separately from data lineage.

### Single-symbol rule engine

The current rule engine is a deterministic daily, long-only, single-symbol
research engine. It supports fixed strategy families and a single position path
for each run. It does not model cross-symbol capital competition, portfolio
cash allocation, rebalance schedules, or multi-asset ledger behavior.

### Universe batch limitation

Universe jobs are local-only batch wrappers around the single-symbol rule
engine. The create phase stores deterministic local-data preflight rows, and the
run phase executes eligible symbols sequentially. Current diagnostics expose
`local_only=true`, `live_provider_calls_executed=false`,
`concurrency_enabled=false`, `pointInTimeUniverse=false`, and uncontrolled
survivorship state. This is useful for batch research, not a PIT universe
backtest.

### Diagnostics vs optimizer boundary

Walk-forward, robustness, compare heatmaps, OOS/parameter readiness, parameter
stability helpers, and bounded grid runners are diagnostic or helper surfaces.
They must not be interpreted as optimizer training, hidden parameter selection,
automatic winner promotion, production strategy selection, or provider-backed
replay. A parameter sweep can only be trusted when the sweep identity and every
member's dataset lineage are stored and reopened.

### Stored run readback

Stored readback is one of the strongest current backtest surfaces. Detail,
history, status, support bundle manifests, reproducibility manifests, export
index, execution trace, robustness evidence, execution-model metadata, and
OOS/parameter readiness are stored-first or readback-oriented surfaces. They
expose `result_authority`, `artifact_availability`, and `readback_integrity`
signals, and they distinguish complete, repaired, legacy, drift-repaired, and
unavailable readback. That protects stored results from silent reconstruction,
but it still does not supply the full dataset-lineage gate defined here.

## 3. Dataset lineage fields

Every trusted backtest output must expose the following dataset-lineage fields
before it can be considered professional-grade. Missing or ambiguous required
fields downgrade the gate state.

| Field | Required contract |
| --- | --- |
| `datasetId` | Stable identifier for the exact dataset snapshot used by the run, sweep, factor panel, or portfolio backtest. Must not be a display label only. |
| `symbolUniverseId` | Stable identifier for the eligible symbol universe. For single-symbol runs, use a scoped single-symbol universe id rather than leaving the universe implicit. |
| `symbolIdentity` | Canonical symbol, security identifier where available, display symbol, name, currency, asset type, and symbol-change lineage. |
| `marketExchange` | Market, exchange, trading venue/session family, currency, and market-specific rule family. |
| `barSource` | Bar source family, source authority, provider/store class, ingestion batch, source file/table, and source timestamp. |
| `adjustedBasis` | Explicit basis: raw, split-adjusted, dividend-adjusted, total-return-adjusted, adjusted-close-only, mixed, or unknown. |
| `corporateActionPolicy` | Split, dividend, merger, spin-off, symbol change, delisting, and restatement policy plus method version. |
| `dividendSplitHandling` | Field-level evidence for dividend and split handling. Partial evidence must stay partial. |
| `calendarSessionPolicy` | Exchange calendar id/version, trading sessions, timezone, open/close conventions, and run-window alignment rules. |
| `halfDayHolidaySuspensionPolicy` | Half-day handling, holiday exclusion, suspension/halt policy, missing session policy, and market-specific limit/halt limitations. |
| `pointInTimeMembershipStatus` | Whether membership was evaluated as of the historical date, with effective dates and as-of timestamps. |
| `survivorshipBiasMarker` | Explicit marker: controlled, uncontrolled, not applicable single symbol, or unknown. Universe and factor tests cannot treat uncontrolled survivorship as professional-grade. |
| `sourceAuthority` | Source authority state, authority source type, right-to-use/display status where relevant, and sanitized reason families. |
| `asOfTimestamp` | Timestamp that bounds what data and membership were known for the simulated historical decision. |
| `generatedAtTimestamp` | Timestamp when this lineage manifest was generated. Must be separate from `asOfTimestamp`. |
| `cacheProvenancePath` | Safe pointer to the local cache, table, manifest, artifact, or storage path used for reproducibility. Consumer outputs should not expose raw secrets or internal runtime paths. |
| `missingStaleFallbackMarkers` | Field-level markers for missing bars, stale bars, fallback fills, degraded source authority, synthetic diagnostics, or unavailable families. |
| `reproducibilityManifest` | Manifest id, manifest version, content hash, execution-assumption fingerprint, bar/universe snapshot hash, and compatible replay contract. |

Current support manifests already expose a partial `dataset_lineage` block with
fields such as source, provider, authority state, requested/actual range,
bar count, and dataset version (`api/v1/schemas/backtest.py`). That block is a
starting point. It is not the complete gate because it does not yet prove
dataset id, universe id, symbol identity lineage, adjusted data contract,
calendar/session contract, PIT membership, missing/stale bar policy, or
snapshot reproducibility hash.

## 4. Gate states

### `professional-ready`

All required dataset-lineage, execution-lineage, readback-integrity, and
surface-specific gates are present, explicit, reproducible, and internally
consistent. No required field is unknown, inferred, mixed, stale, fallback-only,
synthetic, or unverifiable. This state is allowed only after all required gates
for the specific surface pass.

### `research-useful`

The result is deterministic, stored or reproducible enough for research, and its
main assumptions are visible, but at least one professional prerequisite is
missing. Most current single-symbol rule runs belong here when local bars,
execution assumptions, metrics, and readback are present but adjusted data,
corporate-action, calendar, PIT, survivorship, and dataset snapshot contracts
are incomplete.

### `diagnostic-only`

The output is a readiness projection, helper aggregation, support export,
stress/Monte Carlo surface, OOS projection, parameter-stability surface, or
other evidence surface that explains limitations but does not itself establish
trusted historical performance. Current provenance projection, OOS/parameter
readiness, regime-attribution readiness, robustness evidence, and bounded
parameter-grid helper outputs should remain here unless later implementation
tasks store complete lineage for every executed result.

### `blocked`

The output cannot be trusted for the requested use because a required input is
missing, stale, ambiguous, internally inconsistent, or unsupported. Examples:
missing bars, unsupported execution model, absent stored trace when trace is
required, missing PIT universe for a universe/factor surface, unknown adjusted
basis for a total-return claim, or unavailable reproducibility manifest.

### `observation-only`

The output can be read as explanatory context but cannot support performance
acceptance. This state is appropriate for public examples, fixtures, source
labels, provider labels, exploratory diagnostics, incomplete factor panels, and
surfaces that summarize known gaps.

Most current runs should remain `research-useful` or `diagnostic-only` because
current readiness defaults to `research_prototype`, current provenance
projection is diagnostic-only, universe jobs explicitly lack PIT membership and
survivorship control, and current execution model v1 is not an execution-realism
model.

## 5. Surface dependency matrix

| Surface | Required dataset-lineage gate | Current likely state | Additional gate dependencies |
| --- | --- | --- | --- |
| Single-symbol rule run | Single-symbol dataset id, symbol identity, bar source, adjusted basis, corporate-action policy, calendar/session policy, execution model, support manifest, readback integrity. | `research-useful` when stored readback is complete; `blocked` if bars/readback are missing. | v1 execution lineage, fee/slippage assumptions, artifact availability, reproducibility manifest. |
| Parameter sweep | One sweep id plus stable dataset lineage for every parameter member; parameter-grid descriptor hash; deterministic member ordering; no hidden winner promotion. | `diagnostic-only` today unless later stored sweep integration lands. | Stored sweep identity, per-member readback, skipped-member reasons, no optimizer promotion. |
| Universe run | Universe id, PIT membership status, per-symbol identity, local coverage, delisted/inactive handling, survivorship marker, deterministic symbol order. | `research-useful` or `diagnostic-only`; currently not PIT and survivorship is uncontrolled. | Local-only guarantees, compact rows, reason buckets, no provider hydration, no portfolio allocation claim. |
| Factor IC / Rank IC | Factor panel id, observation timestamps, forward-return label lineage, PIT symbol membership, factor formula/version, neutralization metadata where used. | `diagnostic-only` until factor panel lineage exists. | As-of joins, missing observation handling, forward-return generation contract, no lookahead. |
| Factor bucket return | Same as factor IC plus bucket assignment timestamp, bucket methodology, return window, rebalance schedule, and missing-membership handling. | `blocked` for professional use until panel and return lineage are stored. | Bucket membership manifest, forward-return manifest, source authority, survivorship control. |
| Long-short factor portfolio | Long/short membership ids, weights, rebalance dates, borrow/short policy, cash convention, costs, and full factor panel lineage. | `blocked` for professional use; exposure helpers are analysis artifacts, not portfolio return backtests. | Portfolio construction contract, execution model, holdings/weights manifest, benchmark alignment. |
| Portfolio allocation backtest | Portfolio dataset id, security universe id, weights, rebalance schedule, cash/ledger model, price/FX lineage, corporate actions, benchmark, and allocation rules. | `blocked` until portfolio allocation contract lands. | Must not mutate portfolio ledger semantics; needs separate accounting and benchmark gate. |
| Execution trace export | Dataset lineage, execution model, assumptions snapshot, trace source/completeness, row-level fills/actions/costs, and readback integrity. | `research-useful` when stored trace exists; `blocked` when required trace rows are unavailable. | Trace export availability, no synthetic rows, no silent repair without provenance marker. |

## 6. Implementation sequence

1. DATA-040 Metadata-only readback gate
   - Add a stored-first dataset-lineage gate projection to existing rule run
     readback and support manifests without changing engine math or providers.
   - Acceptance: single-symbol readback exposes all required lineage fields as
     present, missing, stale, fallback, or unknown.

2. BTP-001 Stored sweep integration
   - Turn bounded parameter-grid diagnostics into a stored sweep identity with
     per-member lineage and skipped-member reasons.
   - Acceptance: no row can be ranked or compared unless its dataset lineage
     and execution lineage are readable.

3. DATA-041 Adjusted data contract
   - Define and store raw/split-adjusted/dividend-adjusted/total-return basis,
     method version, and adjustment source for daily bars.
   - Acceptance: adjusted-basis unknown blocks professional-grade return claims.

4. DATA-042 Corporate action contract
   - Add explicit dividend, split, symbol-change, delisting, and restatement
     policy evidence to the lineage manifest.
   - Acceptance: partial dividend or split handling remains partial and blocks
     professional-grade gates.

5. DATA-043 Exchange calendar readiness
   - Add exchange calendar/session version, holiday, half-day, suspension, and
     missing-session policy evidence.
   - Acceptance: available-bars-only execution remains research-useful, not
     professional-grade.

6. DATA-044 PIT universe contract
   - Add point-in-time universe membership snapshots, effective dates,
     inactive/delisted symbol handling, and survivorship markers.
   - Acceptance: universe and factor tests fail closed without PIT membership.

7. DATA-045 Factor panel lineage
   - Add factor observation panel id, formula version, as-of timestamp, source
     authority, forward-return label lineage, and missing-observation policy.
   - Acceptance: IC, Rank IC, buckets, and long-short outputs cannot claim
     professional-grade status without panel lineage.

8. BTP-008 Portfolio allocation gate
   - Define portfolio allocation dataset lineage, rebalance schedule, weights,
     cash model, benchmark alignment, FX/price lineage, and ledger boundaries.
   - Acceptance: allocation results remain blocked unless accounting,
     execution, dataset, and benchmark gates all pass.

## 7. Safety constraints

- No fake performance: missing returns, metrics, benchmark values, factor
  returns, attribution values, or sweep cells must remain missing or blocked.
- No synthetic bars presented as real: stress, Monte Carlo, fixtures, and
  generated paths must stay clearly labeled as diagnostic or synthetic.
- No hidden provider fallback: backtest research paths must record whether data
  was local, stored, fallback, degraded, or unavailable; provider hydration must
  not silently fill lineage gaps.
- No lookahead bias: every bar, factor observation, universe row, corporate
  action, benchmark value, and forward-return label needs an explicit as-of
  boundary.
- No survivorship bias overclaim: universe, factor, and portfolio results must
  not claim survivorship control without inactive/delisted membership evidence.
- No `professional-ready` claim without all required gates: a single unknown,
  fallback-only, stale, synthetic, ambiguous, or missing required lineage field
  downgrades the result.
- No trading advice: backtest outputs remain research evidence and data-quality
  objects, not personalized action instructions.

## 8. Acceptance checklist

WolfyStock can call a specific backtest output professional-grade only when all
of the following evidence exists for that output and its surface:

- Dataset identity: `datasetId`, dataset version, manifest version, source
  authority, generated-at timestamp, and reproducibility hash are present.
- Universe identity: `symbolUniverseId`, membership effective dates, PIT
  as-of timestamp, inactive/delisted handling, and survivorship marker are
  present where the surface is not strictly single-symbol.
- Symbol identity: canonical symbol, market, exchange, asset type, currency,
  and symbol-change lineage are present for every tested symbol.
- Bar lineage: bar source, source timestamp, adjusted basis, corporate-action
  policy, dividend/split handling, missing/stale/fallback markers, and
  cache/provenance path are present.
- Calendar lineage: exchange calendar id/version, timezone, sessions,
  holidays, half-days, suspensions/halts, and run-window alignment are present.
- Execution lineage: execution model id/version, signal timing, fill timing,
  fill basis, position sizing, cost/slippage model, terminal fallback, and any
  market-specific execution limitations are explicit.
- Readback integrity: stored summary, metrics, execution model, assumptions
  snapshot, trade rows, equity curve, execution trace, artifact availability,
  and readback integrity are complete or explicitly blocked.
- Surface-specific lineage: sweep id and member manifests for parameter sweeps;
  factor panel and forward-return manifests for factor tests; rebalance,
  weights, cash, FX, benchmark, and ledger manifests for portfolio allocation.
- Bias controls: lookahead, survivorship, missing data, stale data, fallback,
  synthetic data, and source-authority blockers are absent or explicitly
  resolved.
- Safety language: the output avoids personalized action instructions and does
  not promote diagnostic, fixture, fallback, or observation-only evidence into
  professional-grade performance.

If any checklist item is absent, stale, ambiguous, or only diagnostic, the
output must remain `research-useful`, `diagnostic-only`, `blocked`, or
`observation-only` according to the gate states above.
