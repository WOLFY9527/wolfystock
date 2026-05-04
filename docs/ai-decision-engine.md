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

## Local Trace Fixture

For browser smoke verification without a live provider, start the web app in local dev mode and open:

```text
/zh?fixture=analysis-trace
```

Use `/zh?fixture=analysis-trace&trace=open` when the smoke needs to land directly on the trace drawer.
Use `/zh?fixture=analysis-trace&report=open` when the smoke needs to land directly on the full decision report drawer.

The fixture is frontend-only and is enabled only in Vite dev/test mode. It renders a deterministic TEM Home analysis result with `decisionTrace`, execution plan fields, data-source statuses, sanitized LLM metadata, one conflict warning, and limitations.

Safety notes:

- It does not call LiteLLM or any external provider.
- It does not contain raw prompts, system prompts, API keys, or secrets.
- It is fixture data only and not investment advice.
- Production builds do not enable the query-parameter fixture.

## Home Report UX

- The default Home result view is an AI decision dashboard: summary action, score, confidence context, execution plan, and compact evidence/source state.
- Home display identity never uses placeholder names such as `待确认股票`, `Unknown Stock`, `N/A`, or duplicated ticker strings. It prefers available company fields from the report/history payload, renders `Company (TICKER)` when the company is meaningful, renders ticker-only when the name equals or already contains the ticker, and falls back to `--` only when both name and ticker are absent.
- `完整报告` opens a formal financial research report drawer built from existing `standard_report`, dashboard/raw-result fields, trace metadata, and legacy summary fields. It renders 投资结论、重要信息速览、风险警报、利好催化、当日行情、数据透视、技术透视、基本面摘要、作战计划、检查清单 and 数据说明, with missing values shown as `--` / `数据缺失`.
- The report drawer supports `导出 Markdown` and browser print / PDF export (`导出 PDF`). The print flow uses a report-only view so app navigation and action buttons are not part of the printable report.
- `决策来源` opens a compact evidence/trace drawer for decision fields, data used, conflicts, and limitations. Developer details such as provider, model, template, schema status, endpoint, and signal inputs are collapsed by default.
- `完整报告` and `决策来源` live in the main AI decision card top-right action area alongside quiet `复制报告` and `重新分析` actions; there is no separate action/source card.
- The Home UI does not expose raw prompts, system prompts, API keys, or secrets in either drawer.
- Fixture verification paths:
  - `/zh?fixture=analysis-trace`
  - `/zh?fixture=analysis-trace&trace=open`
  - `/zh?fixture=analysis-trace&report=open`

## Limitations

- The trace is generated from existing metadata and does not make an extra LLM call.
- Older stored reports may not contain `decision_trace`; the frontend shows a compact unavailable state.
- Entry/target/stop source attribution is honest but coarse: current values are treated as LLM-derived unless a future backend path records a deterministic source.
