# Data Pipeline R2 Progressive Enrichment

Date: 2026-05-07

Data Pipeline R2 adds a progressive enrichment contract to the existing fast decision data quality report. The quick decision path still depends on required and important data only; optional news, sentiment, and detailed fundamentals are reported through enrichment metadata instead of failing the main analysis.

## Current Runtime Shape

- `dataQualityReport.enrichmentStatus` summarizes optional enrichment as `pending`, `partial`, `complete`, `skipped`, or `failed`.
- `enrichmentSources` is fixed to `news`, `sentiment`, and `detailed_fundamentals`.
- `completedSources`, `pendingSources`, `failedSources`, and `skippedSources` expose source-level state.
- `enrichmentReasons` contains sanitized reason codes only. It must not include raw provider payloads, URLs, query strings, API keys, tokens, cookies, stack traces, or secrets.
- `enrichmentUpdatedAt` and `enrichmentAsOf` provide safe timing metadata.

Timeouts and failures in optional enrichment remain non-blocking gaps. `requiredAvailable`, `dataQualityTier`, and `confidenceCap` still decide whether the fast decision is usable.

## Future Async Update Path

The current production analysis task queue can publish in-progress stages while the task is running, but it does not yet own a safe merge path for late optional provider results after a completed report has already been returned and persisted.

A future async enrichment pass should:

- write late enrichment results to durable owner-scoped task progress or report metadata rows;
- update only `dataQualityReport` enrichment fields and bounded report display metadata;
- preserve the original quick decision fields unless a separate reviewed recalculation path exists;
- emit polling/SSE progress events from durable progress state rather than process-local futures;
- keep reason codes sanitized and developer details collapsed in the UI.

This R2 pass does not add workers, provider circuit enforcement, quota/cost policy changes, provider ordering changes, MarketCache TTL/SWR changes, scanner/backtest/portfolio changes, or LLM routing/prompt changes.
