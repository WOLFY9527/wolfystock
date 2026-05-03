# AI Decision Engine Trace

This note documents the current Home analysis decision path and the `decision_trace` metadata added for auditability.

## Current Engine Path

- Home and Watchlist Analyze submit async work through `POST /api/v1/analysis/analyze`.
- The frontend trigger is `apps/dsa-web/src/api/analysis.ts` `analysisApi.analyzeAsync(...)`.
- Async task state is read from `GET /api/v1/analysis/tasks`, `GET /api/v1/analysis/tasks/{task_id}/progress`, and the task SSE stream.
- The backend entrypoint is `api/v1/endpoints/analysis.py`; it delegates to `src/services/analysis_service.py`, which runs `src/core/pipeline.py`.
- The normal non-agent path calls `src/analyzer.py` `GeminiAnalyzer.analyze(...)` to request a decision-dashboard JSON from LiteLLM.
- `src/core/pipeline.py` injects structured market, technical, fundamental, news, and data-quality blocks into the dashboard, then stabilizes the scalar action/score/trend using deterministic rule scoring when structured inputs are available.
- Final report payloads are assembled in `src/services/analysis_service.py` and persisted through the existing analysis history path.

## Field Attribution

- `action`: rule-derived on the normal structured pipeline when `decision_context.score_breakdown` exists; otherwise LLM-derived or fallback.
- `score`: rule-derived on the normal structured pipeline; the rule path blends market, technical, fundamental, news, and risk adjustments.
- `confidence`: LLM-derived from the dashboard scalar when a model was used; fallback if no model was used.
- `entry`, `target`, `stop`: LLM-derived from `dashboard.battle_plan.sniper_points` in the current path. They are exposed as trace fields but not recalculated by this change.
- Frontend mappings are limited to display normalization, localization, and camelCase conversion; the trace identifies those separately only when a value is known to be frontend-derived.

## LLM Metadata

- Provider/model are read from runtime execution metadata or `result.model_used`, then sanitized.
- Template is reported as `decision_dashboard_v2`.
- Structured output is true when the LLM response parsed as JSON.
- Schema validation uses `src/schemas/report_schema.py` `AnalysisReportSchema`. Validation is lenient: failures are logged and the raw dict still flows through.
- Raw prompts, system prompts, API keys, and secrets are not exposed in `decision_trace`.

## Data Source Metadata

`decision_trace.data_sources` is generated from runtime execution and structured dashboard metadata. It reports compact statuses only: `used`, `missing`, `stale`, `fallback`, or `unknown`.

## Conflict Detection

The first phase is deterministic and non-blocking. It adds warning entries when:

- final action says sell/reduce/avoid while the plan contains buy/add/accumulate wording;
- action says buy while risk text references trend invalidation or severe data gaps;
- data quality is sparse while confidence is high;
- fundamental data is missing while the text makes strong fundamental claims.

These warnings do not change the final decision. They are surfaced only in the optional Home trace drawer.

## Limitations

- The trace is generated from existing metadata and does not make an extra LLM call.
- Older stored reports may not contain `decision_trace`; the frontend shows a compact unavailable state.
- Entry/target/stop source attribution is honest but coarse: current values are treated as LLM-derived unless a future backend path records a deterministic source.
