# Backtest System

## Service Ownership

- Standard historical-evaluation endpoints are owned by `src/services/backtest_service.py`:
  - `POST /api/v1/backtest/run`
  - `POST /api/v1/backtest/prepare-samples`
  - `GET /api/v1/backtest/results`
  - `GET /api/v1/backtest/sample-status`
  - `GET /api/v1/backtest/runs`
  - `GET /api/v1/backtest/performance`
  - `GET /api/v1/backtest/performance/{code}`
  - `POST /api/v1/backtest/samples/clear`
  - `POST /api/v1/backtest/results/clear`
- Rule-backtest endpoints are owned by `src/services/rule_backtest_service.py`:
  - `POST /api/v1/backtest/rule/parse`
  - `POST /api/v1/backtest/rule/run`
  - `POST /api/v1/backtest/rule/compare`
  - `GET /api/v1/backtest/rule/runs`
  - `GET /api/v1/backtest/rule/runs/{run_id}`
  - `GET /api/v1/backtest/rule/runs/{run_id}/status`
  - `GET /api/v1/backtest/rule/runs/{run_id}/support-bundle-manifest`
  - `GET /api/v1/backtest/rule/runs/{run_id}/support-bundle-reproducibility-manifest`
  - `GET /api/v1/backtest/rule/runs/{run_id}/export-index`
  - `GET /api/v1/backtest/rule/runs/{run_id}/execution-trace.json`
  - `GET /api/v1/backtest/rule/runs/{run_id}/robustness-evidence.json`
  - `GET /api/v1/backtest/rule/runs/{run_id}/regime-attribution-readiness.json`
  - `GET /api/v1/backtest/rule/runs/{run_id}/execution-model-metadata.json`
  - `GET /api/v1/backtest/rule/runs/{run_id}/oos-parameter-readiness.json`
  - `GET /api/v1/backtest/rule/runs/{run_id}/execution-trace.csv`
  - `POST /api/v1/backtest/rule/runs/{run_id}/cancel`
  - `POST /api/v1/backtest/rule/universe-jobs`
  - `POST /api/v1/backtest/rule/universe-jobs/{job_id}/run`
  - `GET /api/v1/backtest/rule/universe-jobs/{job_id}/status`
  - `GET /api/v1/backtest/rule/universe-jobs/{job_id}/diagnostics`
  - `GET /api/v1/backtest/rule/universe-jobs/{job_id}/results`

## Current Semantic Boundaries

- `POST /api/v1/backtest/run` is the standard historical-evaluation lane. It
  evaluates stored `AnalysisHistory` snapshots against later market bars and
  does not run the deterministic rule strategy engine. If
  `GET /api/v1/backtest/performance` falls back to stored rule-backtest history
  because no standard summary exists, the payload explicitly reports
  `evaluation_mode=rule_deterministic_fallback` and
  `resolved_source=stored_rule_backtest_runs` so the two lanes are not conflated.
- `POST /api/v1/backtest/rule/run` is a deterministic single-symbol rule
  strategy backtest. It returns single-symbol execution results and research
  metrics; it is not a portfolio-allocation, cross-symbol capital-allocation,
  or portfolio-ledger backtest.
- Universe jobs are batch research wrappers around the existing single-symbol
  rule engine. The create phase only performs local-data preflight; the run
  phase executes symbols one by one in persisted `sequence_index` order and
  emits compact per-symbol rows. This surface is not a portfolio-allocation
  backtest and does not simulate shared capital, weight optimization, or
  multi-asset NAV.
- The current walk-forward surface is diagnostic rolling replay. It reuses the
  same parsed strategy across sliding windows and only reports window-level
  metrics and diagnostics; it does not perform parameter training, optimizer
  search, auto-tuning, or OOS winner selection.
- The current compare heatmap is a stored comparison projection. It derives
  axes and cells from already-persisted compare payloads only, and does not
  trigger parameter grid sweeps, backtest re-execution, provider calls, or any
  new execution.
- The current parameter stability surface helper is an additive scaffold only.
  It plans a deterministic parameter grid and aggregates caller-supplied run or
  evaluation results. It does not execute real strategy backtests, run a hidden
  optimizer, automatically promote winners, select live strategies, change
  engine math, call providers, or perform portfolio-allocation backtests.
- The bounded parameter grid runner remains an internal `RuleBacktestService`
  diagnostic-only helper. It only replays bounded single-symbol diagnostics
  when the caller already supplies bars and a parsed strategy; it exposes no new
  API/schema/frontend surface, creates no persisted public run identity, and
  does not promote `request_id`, `external_run_id`, or `planned_run_id` into
  stored public run semantics.
- When `robustness_config` is omitted, the current robustness-analysis surface
  still emits stored robustness evidence with defaults:
  `walk_forward(train=24,test=12,step=12,max_windows=4)`,
  `monte_carlo(simulation_count=12,noise_scale=0.75,seed=derived)`, plus fixed
  stress scenarios. This remains research-prototype evidence, not an optimizer.

## Async And Background Execution

- Rule-backtest detail / status / history payloads and universe job status / diagnostics now include additive `professionalReadiness` diagnostics so the API can state what is and is not professionally ready.
- The current default conclusion is fixed to `overall_state=research_prototype` and `professional_quant_ready=false`.
- These readiness fields are advisory-only: they do not change single-symbol calculations, fill timing, fee/slippage math, benchmark math, stored-result semantics, or universe execution order, and they do not add live provider calls.

- `POST /api/v1/backtest/rule/run` is asynchronous by default and returns one of `queued / parsing / running / summarizing / completed / failed / cancelled`.
- Pass `wait_for_completion=true` to run inline and return the full completed payload.
- `GET /api/v1/backtest/rule/runs/{run_id}/status` is the lightweight polling endpoint for background progress.
- `GET /api/v1/backtest/rule/runs/{run_id}/support-bundle-manifest` returns the compact stored-first support bundle manifest for one rule-backtest run. It reuses the existing detail readback summaries for `run_timing`, `run_diagnostics`, `artifact_availability`, `readback_integrity`, and normalized `result_authority.domains`, then adds only lightweight `artifact_counts` for handoff, AI debugging, and automation scripts; it does not inline heavy payloads such as `trades`, `equity_curve`, `audit_rows`, or the full `execution_trace` by default.
- `GET /api/v1/backtest/rule/runs/{run_id}/support-bundle-reproducibility-manifest` returns the compact reproducibility manifest for the same run. It reuses the same `run_timing`, `run_diagnostics`, `artifact_availability`, and `readback_integrity` blocks as the support bundle manifest, then adds `execution_assumptions_fingerprint` plus the reduced `result_authority.domains.execution_trace` summary for migration, replay, and reproducibility checks.
- `GET /api/v1/backtest/rule/runs/{run_id}/export-index` returns the compact discovery index for the currently exportable artifacts of one rule-backtest run. The current stable set is: `support_bundle_manifest_json`, `support_bundle_reproducibility_manifest_json`, `execution_trace_json`, `execution_trace_csv`, `robustness_evidence_json`, `regime_attribution_readiness_json`, `execution_model_metadata_json`, and `oos_parameter_readiness_json`. Both manifests expose their readable API paths directly; execution-trace JSON/CSV, stored-robustness evidence JSON, diagnostic regime-attribution readiness projection JSON, read-only execution-model metadata JSON, and OOS/parameter-readiness projection JSON also expose real API paths instead of remaining service-file-only hints. Trace availability is still determined from the resolved detail readback `execution_trace.rows`, so older runs without exportable trace rows return `available=false` with `execution_trace_rows_missing`; robustness evidence availability is reported independently as `stored_robustness_analysis_present / stored_robustness_analysis_missing`. Regime-attribution readiness remains a diagnostic/readiness projection and does not claim validated institutional PnL attribution; execution-model metadata exposes only the current/default rule-backtest execution model v1 guardrails without rerunning the engine; OOS/parameter-readiness remains stored-first and only projects stored robustness/walk-forward evidence or compare/parameter evidence supplied to internal service/helper calls. The public GET itself does not accept compare payload input.
- `GET /api/v1/backtest/rule/runs/{run_id}/execution-trace.json` and `GET /api/v1/backtest/rule/runs/{run_id}/execution-trace.csv` are the heavy trace exports of the support bundle surface: the JSON payload is optimized for AI and automation consumers, while the CSV payload is optimized for operator review and spreadsheets. Both share the same stored-first trace-availability gate as the export index and return `409 export_unavailable` when trace rows are missing instead of faking an empty export.
- `GET /api/v1/backtest/rule/runs/{run_id}/robustness-evidence.json` returns the stored robustness-evidence export. It directly reuses the stored `robustness_analysis` payload; if that payload is missing from the stored run, the endpoint returns `409 export_unavailable` instead of recalculating robustness on demand.
- `GET /api/v1/backtest/rule/runs/{run_id}/execution-model-metadata.json` returns the read-only metadata export for the current/default rule-backtest execution model v1. The payload explicitly keeps the current deterministic engine behavior and guardrails: fee/slippage are assumptions when present; market impact, spread simulation, partial fills, halt/limit-up/limit-down modeling, tax/stamp-duty modeling, volume participation caps, PIT-universe guarantees, adjusted-data guarantees, and provider/live-call requirements are not added. The export remains `diagnostic_only/readiness_only/decision_grade=false`; `v1` is the only supported/current/default executable model, while future `v2` posture remains unavailable/fail-closed.
- `GET /api/v1/backtest/rule/runs/{run_id}/oos-parameter-readiness.json` returns a combined OOS and parameter-readiness export for one rule-backtest run. It is diagnostic/readiness-only and stored-first: the OOS section reads `walk_forward_oos_evidence` derived from stored `robustness_analysis.walk_forward`, while the parameter section only projects compare/parameter-stability evidence supplied to internal service/helper calls. This public GET has only `run_id` read semantics and does not accept compare payload, parameter evidence, or request-body input; it does not rerun strategies, optimizers, parameter sweeps, bounded grids, provider/live calls, or mutate stored run results. Missing evidence returns explicit `unavailable` sections and at most `partial/unavailable` overall state.
- `POST /api/v1/backtest/rule/runs/{run_id}/cancel` is a best-effort cancel endpoint: unfinished runs are marked `cancelled`, while already-finished runs keep their final state.
- `POST /api/v1/backtest/rule/universe-jobs` creates a stored local-only universe job scaffold. The create phase performs local daily-bar preflight only: it deduplicates and sorts normalized symbols, persists `sequence_index`, records compact per-symbol readiness rows, and defaults to a 500-symbol cap. Symbols without local daily bars are marked `skipped / blocked_missing_local_data`. The create endpoint does not execute single-symbol rule backtests, call provider hydration, write heavy run details, enable worker concurrency, or make DuckDB a runtime source of truth.
- `POST /api/v1/backtest/rule/universe-jobs/{job_id}/run` synchronously executes an existing local-only universe job in sequence. The path reads only local `StockDaily` rows and does not call `_ensure_market_history`, provider fallback, or DuckDB; symbols run one at a time in persisted `sequence_index` order through the existing rule backtest engine. Per-symbol failures write compact failed rows and do not abort later symbols. Re-running an already executed job is rejected to avoid duplicate job/symbol results.
- `GET /api/v1/backtest/rule/universe-jobs/{job_id}/status` returns lightweight universe job metadata and progress counters, including derived `processed_count`; `GET /api/v1/backtest/rule/universe-jobs/{job_id}/diagnostics` returns read-only compact aggregation: progress summary, reason buckets, top/worst metric leaders, local-data coverage counts, and explicit `local_only=true / live_provider_calls_executed=false / concurrency_enabled=false` guarantees. This diagnostics surface does not re-run calculations, call providers, read raw traces, or inline full per-symbol drill-down. `GET /api/v1/backtest/rule/universe-jobs/{job_id}/results` returns paginated compact symbol rows with a page-size cap of 100 and supports filtering/sorting by `status`, `reasonCode`, `symbol` prefix, inferred `market`, and `sequence_index / total_return_pct / max_drawdown_pct / win_rate_pct / trades_count / elapsed_ms`. Executed compact rows include only table/status fields: symbol/status/reason, `total_return_pct`, `max_drawdown_pct`, `win_rate_pct`, `trades_count`, runtime, and small local-data diagnostics; raw trades, equity curves, and execution traces are not stored by default.
- Universe readiness diagnostics also make these boundaries explicit: `localDataCoverageState`, `pointInTimeUniverse=false`, `survivorshipBiasState=uncontrolled`, and `providerCalls=false`.
- `POST /api/v1/backtest/rule/compare` is the stored-first compare-runs read path: it only reads already-persisted completed runs, does not re-execute backtests, and currently returns the smallest trustworthy comparison surface across metadata, `parsed_strategy`, core metrics, benchmark summary, `execution_model`, each run's `result_authority`, plus seven additive top-level summaries: `market_code_comparison`, `period_comparison`, `comparison_summary`, `parameter_comparison`, `robustness_summary`, `comparison_profile`, and `comparison_highlights`. `market_code_comparison` only consumes persisted `metadata.code` from the compare items, normalizes the code into a `cn / hk / us` market tag, and explicitly classifies `same_code / same_market_different_code / different_market / partial_metadata / unavailable_metadata`; only `same_code` is marked as `state=direct` with `directly_comparable=true`. `period_comparison` only reads persisted `metadata.period_start/period_end` bounds from the compare items, never re-runs the backtest, and explicitly classifies the period relationship as `identical / overlapping / disjoint / partial / unavailable`; `comparison_summary` always picks the first comparable run in request order as the baseline and emits deltas/comparability diagnostics for a narrow trusted metric set; `parameter_comparison` only uses persisted `parsed_strategy.strategy_spec` plus parsed-strategy authority diagnostics to answer whether the runs are comparable as the same normalized strategy family/type and which parameter keys are shared, different, or missing; `robustness_summary` only reuses those four already-computed compare layers and emits a compact overall `highly_comparable / partially_comparable / context_limited / insufficient_context` state plus per-dimension `aligned / partial / divergent / unavailable` summaries for `market_code / metrics_baseline / parameter_set / periods`; `comparison_profile` then classifies the compare request into one deterministic primary mode: `same_strategy_parameter_variants / same_code_different_periods / same_market_cross_code / cross_market_mixed / mixed_context / insufficient_context`; `comparison_highlights` finally reuses only trusted `comparison_summary.metric_deltas`, `robustness_summary`, and `comparison_profile` to emit compact per-metric `winner / tie / limited_context_winner / limited_context_tie / unavailable` highlights instead of silently ranking every visible number.
- `GET /api/v1/backtest/rule/runs/{run_id}` remains the full-detail endpoint and includes `execution_trace`, trades, and audit data.
- Deterministic indicator strategies now support additive fixed-percentage risk controls on top of the existing `moving_average_crossover / macd_crossover / rsi_threshold` signal families: `fixed stop-loss`, `take-profit`, and `trailing stop`. When the natural-language strategy includes bounded percentage rules such as `stop loss 5%`, `take profit 10%`, or `trailing stop 8%`, the parsed payload preserves them under `parsed_strategy.strategy_spec.risk_controls.{stop_loss_pct,take_profit_pct,trailing_stop_pct}`, and execution still follows the existing “signal on close, exit on the next bar open” fill semantics. The scope remains intentionally small: single symbol, single position, percentage thresholds only, with no parameter optimization, multi-asset semantics, or portfolio-level risk engine.
- The `result_authority` object on detail/history payloads now also exposes replay/audit reopen diagnostics: `replay_payload_source` / `replay_payload_completeness` / `replay_payload_missing_sections` plus `audit_rows_source` / `daily_return_series_source` / `exposure_curve_source`. These fields distinguish between directly persisted payloads, sections repaired from persisted audit rows, legacy replay payload rebuilt from stored run artifacts, and omitted/unavailable states.
- `execution_model` reopen now follows the same stored-first rule: the service first reads `summary.execution_model`, then falls back to persisted `summary.request.execution_model`, and only derives from stored assumptions / row/request when neither snapshot exists. `result_authority` now also exposes `execution_model_source` / `execution_model_completeness` / `execution_model_missing_fields` so consumers can distinguish a directly persisted snapshot, a repaired stored snapshot, and a legacy-derived execution model.
- `trade_rows` reopen now follows the same stored-first rule: detail reads prefer persisted `rule_backtest_trades`, and `result_authority` now also exposes `trade_rows_source` / `trade_rows_completeness` / `trade_rows_missing_fields`. Older runs with partial trade-row helper JSON (`entry_rule_json` / `exit_rule_json` / `notes`) still return a stable `trades` payload, but are explicitly marked as `stored_rule_backtest_trades+compat_repair` / `stored_partial_repaired`; runs whose summary metrics indicate trades but whose persisted trade rows are missing are now explicitly marked `unavailable` instead of silently looking like a complete empty list.
- To keep reopen/debug flows from having to infer artifact presence from `result_authority` omissions or scattered null checks, the status/detail/history read paths now all expose a structured `artifact_availability` summary and mirror the same block into `summary.artifact_availability`. The summary answers only the narrow persisted-availability question: whether the run still has a reopenable stored summary, parsed strategy, metrics, execution model, comparison payload, trade rows, equity curve, execution trace, run diagnostics, and run timing. When older summaries do not contain this block, the service derives a compatibility view from current persisted storage; when the stored summary has drifted from live trade-row storage, the response is explicitly marked as a live-storage repair instead of replaying stale booleans.
- To make the trust level of a reopened response easier to evaluate directly, the status/detail/history read paths now also expose a compact `readback_integrity` summary. It does not duplicate payload contents; it only answers the integrity question for the current read path: whether legacy fallback was used, whether live-storage repair was used, whether summary/storage drift exists, which drift domains are affected, which key summary fields are still missing, and whether the current integrity level is `stored_complete`, `stored_repaired`, `legacy_fallback`, or `drift_repaired`. The summary is intentionally built on top of the existing `result_authority` and `artifact_availability` signals instead of creating a second parallel provenance system.
- To make the authority contract more uniform across detail/history surfaces, `result_authority` now also includes a versioned normalized view: `contract_version` plus `domains`. Each `domains.<name>` entry uses the same five keys: `source`, `completeness`, `state`, `missing`, and `missing_kind`. The older flat authority fields remain in place for compatibility.

## P5 Web Usability Layer

- `/backtest` remains the configuration-and-launch page. This phase does not redesign the working standard or rule-backtest backend flow; it tightens input grouping, button wording, and state copy so users can understand the next step more easily.
- `/backtest/results/:runId` now keeps a dedicated run-status card above the result summary and chart workspace. While a rule run is active, the page polls `GET /api/v1/backtest/rule/runs/{run_id}/status`; once the run reaches `completed / failed / cancelled`, polling stops automatically.
- `/backtest/compare?runIds=...` now exists as the first minimal compare workbench route. It consumes the existing `POST /api/v1/backtest/rule/compare` stored-first response directly instead of reloading multiple result details and inventing frontend-only conclusions. The `History` tab on `/backtest/results/:runId` still pins the current run as the baseline, lets users select additional completed runs, and now exposes an `Open compare workbench` action that forwards those ordered run ids into the new page for compact compare-summary / robustness / profile / highlights / market / period / parameter sections.
- Active rule runs now surface the full lifecycle more clearly: `parsing / queued / running / summarizing / completed / cancelled / failed`. The UI also exposes a safe `Cancel run` action during cancellable stages and still reuses the existing `POST /api/v1/backtest/rule/runs/{run_id}/cancel` contract.
- The result page promotes user-facing summary metrics first: total return, relative benchmark or buy-and-hold comparison, max drawdown, trade count, win rate, and final equity. Raw parameters, execution assumptions, technical notes, and history remain available as secondary detail.
- `execution_trace` still comes from the existing detail payload, but the Web UI now defaults to a lighter “highlights” view that focuses on buy/sell actions, fallback notes, and exceptions. Users can still switch to the full trace and export CSV / JSON.
- Historical Evaluation now explains LocalParquet versus fallback in simpler product language. The raw diagnostics fields `requested_mode / resolved_source / fallback_used` remain available under a disclosure so the main flow stays readable.

## Release Handoff Status

- The current branch's backend backtest contract has converged on stored-first and additive-first read surfaces: robustness, compare, support bundle, execution-trace export, diagnostics, and timing are exposed through existing read paths or read-only export paths, without requiring the frontend to re-run or reassemble backend conclusions.
- The Web `/backtest` and `/backtest/results/:runId` dashboard panels read `strategy_spec.risk_controls` and `robustness_analysis` additively; they do not alter strategy parsing, execution, polling, cancellation, compare APIs, or historical-result data flow.
- The Web `/portfolio` attribution dashboard likewise reads additive `portfolio_attribution`, `account_attribution`, and `industry_attribution` blocks without changing ledger writes, snapshot computation, risk alerts, import, or sync semantics.
- Slices 14-16 completed route/page-level bundle hardening, keyboard and ARIA-tooltip regression coverage, focused tests, lint, production build, and production-preview browser regression; the Vite large-chunk warning is currently cleared.
- No backend, schema, API, or additive-contract changes were made after regression close; `slice_report_14.json`, `slice_report_15.json`, `slice_report_16.json`, and subsequent slice reports are local handoff artifacts and are intentionally excluded from git.
- Known non-blockers: there is no chart-heavy advanced visualization layer yet; future work can add richer charts, deeper compare visuals, or expanded accessibility semantics, but those are not release blockers for the current handoff.
- Safety/rollback posture: the new Web panels and chunk split are frontend additive/read-only layers, so a release rollback can first revert the relevant frontend dashboard/lazy-loading commits while leaving the backend stored-first read and export surfaces compatible with existing consumers.

## Local US Parquet Priority

- US daily history first reads `LOCAL_US_PARQUET_DIR`.
- If `LOCAL_US_PARQUET_DIR` is unset, the code falls back to `US_STOCK_PARQUET_DIR` for backward compatibility.
- A local parquet hit reports `resolved_source=LocalParquet` and skips online fetching.
- If local parquet is missing or invalid, the backtest flow follows the existing fetch fallback path and exposes `requested_mode / resolved_source / fallback_used` in responses.

## Run The API Locally

```bash
.venv/bin/uvicorn api.app:app --host 127.0.0.1 --port 8000
```

Optional environment variables:

```bash
export LOCAL_US_PARQUET_DIR=/path/to/local/us/parquet
# Use only for legacy compatibility
export US_STOCK_PARQUET_DIR=/path/to/local/us/parquet
```

## Smoke Scripts

- The committed smoke scripts currently checked into the repo automatically:
  - boot a temporary uvicorn server
  - disable admin auth
  - create a temporary database
  - prepare a temporary `LOCAL_US_PARQUET_DIR` fixture
  - run assertions and clean everything up

- Standard backtest API smoke:

```bash
python3 scripts/smoke_backtest_standard.py
```

- Rule backtest API smoke:

```bash
python3 scripts/smoke_backtest_rule.py
```

- Run both:

```bash
python3 scripts/smoke_backtest_standard.py && python3 scripts/smoke_backtest_rule.py
```

## Known Assumptions And Limits

- Real local-parquet reads in production still require `pyarrow` or `fastparquet`; when a parquet engine is unavailable, the repo smoke scripts inject a test-only shim so the `LOCAL_US_PARQUET_DIR` priority path and async endpoints can still be validated.
- Synchronous rule backtests still depend on market data being available locally or through the existing data-source fallback chain.
- `execution_trace` detail and CSV / JSON exports treat persisted `audit_rows` as the source of truth; older runs that do not store it are rebuilt on read and marked with `trace_rebuilt`.
- The `execution_model` detail field is now normalized into a stable shape during reopen as well; older runs with only partial execution-model snapshots are marked as `stored_partial_repaired` with explicit missing-field diagnostics instead of returning a structurally incomplete payload.
- The `trade_rows` detail field is now normalized into a stable shape during reopen as well; older runs with partial persisted trade-row helper JSON are marked as `stored_partial_repaired` with explicit missing-field diagnostics, and runs whose run row still reports trades while persisted trade rows are absent are marked as `unavailable` instead of being mistaken for complete zero-trade results.
- Replay-visualization reopen now follows the same stored-first rule: non-empty persisted `summary.visualization.audit_rows` / `daily_return_series` / `exposure_curve` sections stay authoritative, while older runs with missing or empty replay sections are explicitly marked as `stored_partial_repaired`, `derived_from_stored_run_artifacts`, or `unavailable` instead of silently presenting regenerated payloads as fully persisted data.
