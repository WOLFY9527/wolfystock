# T-925 Home LLM Evidence Input Hardening Audit

Task ID: T-925
Mode: docs-only audit artifact for a task with `READ-ONLY-AUDIT` runtime
semantics. No runtime code, prompt, provider, frontend, config, CI, or storage
behavior was changed by this task.

## Executive Verdict

T-923 and T-924 established the right downstream contract: Home responses now
mirror `singleStockEvidencePacket`, plus its `fundamentalsEarnings` and
`newsCatalysts` sub-contracts. The remaining gap is upstream. The Home LLM still
receives mixed legacy context:

- a highest-salience finance table that depends on `fundamental_context`, even
  though US/HK `fundamental_context` can be unavailable;
- later compact structured finance snippets from supplemental providers;
- flattened `news_context` prose instead of bounded top-N citation items;
- data-quality metadata that explains degradation but is not itself evidence.

The safe next step is not a prompt rewrite or provider expansion. It is an
additive, deterministic Home LLM evidence input adapter that converts
`singleStockEvidencePacket`, `fundamentalsEarnings`, and `newsCatalysts` into a
bounded evidence index before the analyzer prompt is built. The adapter should
preserve missing/degraded/blocked notes, authority/freshness labels, and
no-advice boundaries, while excluding raw provider payloads, diagnostics,
article bodies, internal labels, secrets, and execution-grade trading language.

## Scope And Method

This audit inspected current Home/single-stock LLM input assembly, response
mirrors, report serialization, parser/fallback behavior, and recent packet tests
without changing runtime behavior or making live provider calls.

Primary files inspected:

- `src/core/pipeline.py:538-994`
- `src/core/pipeline.py:1076-1185`
- `src/core/pipeline.py:2705-3815`
- `src/analyzer.py:82-149`
- `src/analyzer.py:1148-1335`
- `src/analyzer.py:1466-1890`
- `src/services/analysis_service.py:693-977`
- `src/services/analysis_service.py:1397-1737`
- `src/services/single_stock_evidence_packet.py:10-698`
- `src/services/single_stock_fundamentals_earnings_normalizer.py:14-675`
- `src/services/single_stock_news_catalyst_extractor.py:15-658`
- `src/services/report_renderer.py:3120-3245`
- `src/services/report_renderer.py:3731-3895`
- `api/v1/schemas/history.py:147-264`
- `api/v1/endpoints/analysis.py:1120-1285`
- `tests/services/test_single_stock_evidence_packet.py`
- `tests/services/test_single_stock_fundamentals_earnings_normalizer.py`
- `tests/services/test_single_stock_news_catalyst_extractor.py`
- `tests/services/test_analysis_research_readiness_projection.py:502-775`

## 1. Current Home LLM Input Path Inventory

### 1.1 Pipeline input assembly

`StockAnalysisPipeline.process_single_stock()` is the current upstream assembly
point. It gathers:

- `fundamental_context` through `DataFetcherManager.get_fundamental_context()`,
  with fail-open fallback and execution-stage logging (`src/core/pipeline.py:538-557`);
- optional news intelligence through `search_comprehensive_intel()`, with
  timeout/fallback behavior and flattened `news_context`
  (`src/core/pipeline.py:601-703`);
- optional social sentiment, appended into `news_context` when present
  (`src/core/pipeline.py:705-760`);
- US supplemental categories for quote, fundamentals, earnings, history, and
  technicals only (`src/core/pipeline.py:1076-1185`);
- multidimensional structured blocks for technicals, fundamentals, earnings,
  sentiment, catalyst, realtime, and data quality (`src/core/pipeline.py:934-953`);
- `data_quality_report`, built before the LLM call and attached to
  `enhanced_context` (`src/core/pipeline.py:960-967`).

The analyzer call occurs before `singleStockEvidencePacket` is built:

- `self.analyzer.analyze(enhanced_context, news_context=...)` is invoked at
  `src/core/pipeline.py:986-994`;
- score caps and structured runtime summaries are applied only after the LLM
  result exists (`src/core/pipeline.py:1019-1046`).

### 1.2 Analyzer prompt builder

`Analyzer.analyze()` delegates prompt construction to `_format_prompt()` and
then calls the configured LLM (`src/analyzer.py:1148-1335`). The current prompt
builder includes:

- data-quality summary fields from `data_quality_report` and `data_quality`
  (`src/analyzer.py:1466-1527`);
- a high-salience finance table from `fundamental_context.earnings` and
  `fundamental_context.dividend` (`src/analyzer.py:1641-1684`);
- later compact structured snippets for `fundamentals`, `earnings_analysis`,
  and `sentiment_analysis` (`src/analyzer.py:1686-1719`);
- a flattened `news_context` text block (`src/analyzer.py:1794-1813`);
- output fields that still include decision-shaped legacy keys
  (`src/analyzer.py:1859-1888`).

There is no prompt consumption of `singleStockEvidencePacket`,
`fundamentalsEarnings`, or `newsCatalysts` today.

### 1.3 Parser, retry, and placeholder behavior

The analyzer can parse, repair, retry, and fill missing mandatory fields:

- content integrity checks and placeholder fill live in `src/analyzer.py:82-149`;
- integrity retry can append the original prompt plus the previous response and
  complement instructions, increasing prompt size and creating a future
  duplication risk if evidence blocks are appended naively
  (`src/analyzer.py:2017-2072`);
- post-LLM data-quality caps can suppress score/action confidence, but they do
  not change what the LLM originally saw (`src/core/pipeline.py:1169-1349`).

### 1.4 Response and report mirrors

`AnalysisService._build_report_payload()` builds public mirrors after the LLM
result is returned. It attaches `researchReadiness`, `evidenceCoverageFrame`,
`dataQualityReport`, and `singleStockEvidencePacket` into response/report/meta
locations (`src/services/analysis_service.py:693-866`).

`_build_home_single_stock_evidence_packet()` creates the packet from
`structuredAnalysis`, runtime data, `dataQualityReport`, and `news_context`, then
adds:

- `fundamentalsEarnings` from
  `build_single_stock_fundamentals_earnings_normalizer_v1()`;
- `newsCatalysts` from
  `build_single_stock_news_catalyst_extractor_v1()`
  (`src/services/analysis_service.py:945-977`).

This proves the packet is a response/report mirror today, not an LLM input.

### 1.5 Existing citation/evidence-adjacent sections

Current report rendering uses structured analysis and dashboard fields, not the
new packet:

- standard report payloads read fundamentals, earnings, sentiment, and dashboard
  intelligence from `dashboard` / `structured_analysis`
  (`src/services/report_renderer.py:3120-3245`,
  `src/services/report_renderer.py:3731-3895`);
- history schemas can hydrate `singleStockEvidencePacket` into report/meta
  mirrors (`api/v1/schemas/history.py:147-264`);
- endpoint report rebuilding relies on existing report/details hydration paths,
  so response/report compatibility should be regression-tested when report
  sections start citing packet evidence (`api/v1/endpoints/analysis.py:1120-1285`).

## 2. Current Flow Map And Evidence Loss Points

### 2.1 Source/runtime context to prompt

Current LLM input flow:

1. Providers and local runtime assemble raw and normalized context in
   `StockAnalysisPipeline`.
2. `_build_multidim_blocks()` creates structured blocks for fundamentals,
   earnings, sentiment, catalyst, technicals, and data quality.
3. `build_data_quality_report()` compresses missing/stale/fallback/timeout
   states into guardrail metadata.
4. `_format_prompt()` injects legacy tables, structured snippets, data-quality
   metadata, and flattened `news_context`.
5. The LLM response is parsed, repaired, capped, and converted to public report
   payloads.
6. `singleStockEvidencePacket`, `fundamentalsEarnings`, and `newsCatalysts` are
   built after the LLM response and mirrored into public response/report fields.

### 2.2 Fundamentals, earnings, and valuation

Where useful evidence exists:

- `_build_fundamentals_block()` merges FMP, Finnhub, YFinance, Alpha Vantage,
  and `fundamental_context` candidates into field sources, periods, summary
  flags, and normalized metrics (`src/core/pipeline.py:3264-3575`);
- `_build_earnings_analysis_block()` normalizes quarterly series, derived
  growth, reporting basis, and fallback flags (`src/core/pipeline.py:3578-3673`);
- `fundamentalsEarnings` converts these blocks into bounded refs with `id`,
  domain, label, value, period, as-of metadata, source tier, provider authority,
  freshness, confidence, and limitations
  (`src/services/single_stock_fundamentals_earnings_normalizer.py:380-418`).

Where evidence is dropped or over-trusted:

- the most prominent finance prompt section still depends on
  `fundamental_context`, which is an unsupported or unavailable path for common
  US/HK cases;
- supplemental US evidence is injected later and less prominently;
- the prompt has no bounded evidence IDs, so final report fields cannot cite the
  strongest financial refs deterministically;
- `fundamental_context_unavailable` is detected by the packet/normalizer but is
  not yet used to constrain the LLM's finance wording.

### 2.3 News, catalysts, and sentiment

Where useful evidence exists:

- `search_comprehensive_intel()` can produce multi-dimension intelligence;
- `_collect_news_items_from_intel()` keeps title, snippet, URL, dimension, and
  date (`src/core/pipeline.py:2705-2722`);
- `_build_sentiment_analysis_block()` classifies collected items, but returns
  empty `top_positive_items` and `top_negative_items`
  (`src/core/pipeline.py:3687-3815`);
- `newsCatalysts` can extract bounded `topNewsItems`, `topCatalystItems`, and
  sentiment summaries, including degraded context-only fallback and timeout
  states (`src/services/single_stock_news_catalyst_extractor.py:69-205`).

Where evidence is flattened or duplicated:

- `format_intel_report()` creates long `news_context` prose;
- social sentiment can be appended into the same string;
- the prompt injects that string directly;
- `newsCatalysts` currently exists after the LLM call, so its top-N and
  citation-safe items do not guide the model.

### 2.4 Data quality and readiness

`dataQualityReport`, `researchReadiness`, and `evidenceCoverageFrame` are
truthful guardrails, but they are not citation evidence. They should continue to
constrain tone, confidence, and missing-evidence statements, while the new
adapter should supply evidence IDs and short summaries.

### 2.5 Diagnostics and execution logs

Execution stages, provider chains, `decision_trace`, prompt debug flags, context
snapshots, router diagnostics, and persisted raw-ish payload references are
diagnostic or operational data. They must not be promoted into public citations
or LLM evidence text.

## 3. LLM-Safe Evidence Input Adapter Contract

Future T-928 should add a pure, deterministic adapter, tentatively:

```text
HomeLlmEvidenceInputV1
```

The adapter should be assembled before `Analyzer._format_prompt()` is called.
Because the existing `AnalysisService._build_home_single_stock_evidence_packet()`
is post-LLM, T-928 should either:

- share a pure packet-building helper that can run in the pipeline before the
  analyzer call; or
- build the same packet-shaped payload in the pipeline from `structuredAnalysis`,
  runtime data, `dataQualityReport`, and `news_context`, then pass only the
  adapter output into the prompt.

The adapter must not change provider order, cache behavior, LLM model routing,
endpoint contracts, or report rendering in T-928.

### 3.1 Adapter input

Use only already-assembled, sanitized runtime objects:

- `singleStockEvidencePacket.domains`
- `singleStockEvidencePacket.sourceSummary`
- `singleStockEvidencePacket.missingEvidence`
- `singleStockEvidencePacket.blockingReasons`
- `singleStockEvidencePacket.nextEvidenceNeeded`
- `singleStockEvidencePacket.noAdviceBoundary`
- `fundamentalsEarnings.evidenceRefs`
- `fundamentalsEarnings.missingEvidence`
- `fundamentalsEarnings.blockingReasons`
- `fundamentalsEarnings.nextEvidenceNeeded`
- `newsCatalysts.topNewsItems`
- `newsCatalysts.topCatalystItems`
- `newsCatalysts.sentimentSummary`
- `newsCatalysts.missingEvidence`
- `newsCatalysts.blockingReasons`
- `newsCatalysts.nextEvidenceNeeded`
- `dataQualityReport` guardrail fields already used by the prompt

### 3.2 Adapter output

Emit one compact prompt-ready object, not multiple unbounded text blocks:

```text
contractVersion: home_llm_evidence_input_v1
packetState: ready | observe_only | insufficient | blocked | waiting
evidenceIndex: EvidenceRef[]
domainSummaries: DomainSummary[]
missingEvidenceNotes: EvidenceNote[]
degradedEvidenceNotes: EvidenceNote[]
blockingNotes: EvidenceNote[]
noAdviceBoundary: string[]
promptUseRules: string[]
```

`EvidenceRef` should be short and citation-ready:

```text
id
domain
summary
sourceId
sourceTier
providerAuthority
freshness
asOf
period
confidence
limitations
```

No field may contain raw provider JSON, article bodies, stack traces, credentials,
router internals, cache keys, environment labels, prompt dumps, or account/broker
payloads.

### 3.3 Domain summaries

For every packet domain, include a short summary:

```text
domain
status: available | degraded | missing | blocked | pending | stale
authorityLabel: scoreGrade | observationOnly | diagnosticOnly | unavailable
freshnessLabel: fresh | delayed | stale | unknown | unavailable
evidenceRefIds: string[]
notes: string[]
```

Notes must be deterministic and bounded. They should name missing, degraded, or
blocked evidence without implying that unsupported data is available.

### 3.4 Missing/degraded/blocked notes

Use controlled notes derived from existing reason codes:

- `fundamental_context_unavailable`
- `provider_timeout`
- `news_context_only`
- `fallback_proxy_evidence`
- `stale_evidence`
- `manual_unknown`
- `unsupported_market`
- `no_structured_items`
- `no_score_grade_source`

The adapter should translate those into short consumer-safe evidence statements,
not expose internal provider/router details.

### 3.5 No-advice boundary

The adapter-added prompt text should state that evidence supports research
explanation only. It must not add or strengthen buy/sell/order/trade/broker
execution language. If legacy prompt output keys still contain decision-shaped
field names, the adapter should only constrain evidence grounding and consumer
copy, not rename fields in T-928.

## 4. Domain Citation/Input Contract

### 4.1 Fundamentals

Input source:

- `fundamentalsEarnings.evidenceRefs` where `domain == fundamentals`
- `singleStockEvidencePacket.domains.fundamentals`
- relevant `dataQualityReport` missing/freshness/cap reason codes

Allowed prompt content:

- top metrics with `id`, label, normalized value, period/as-of, source tier,
  provider authority, freshness, and limitations;
- explicit unavailable/degraded notes when refs are absent or observation-only.

Must not include:

- raw statement payloads;
- unsupported `fundamental_context` tables presented as available;
- confidence wording that exceeds source authority.

### 4.2 Earnings

Input source:

- `fundamentalsEarnings.evidenceRefs` where `domain == earnings`
- `singleStockEvidencePacket.domains.earnings`

Allowed prompt content:

- bounded quarterly or derived growth refs;
- period/reporting-basis labels;
- "insufficient evidence" notes when only fallback/proxy or no series exists.

Must not include:

- unqualified earnings trend claims;
- uncited quarter-over-quarter narratives;
- raw earnings provider payloads.

### 4.3 Valuation

Input source:

- `fundamentalsEarnings.evidenceRefs` where `domain == valuation`
- `singleStockEvidencePacket.domains.valuation`

Allowed prompt content:

- bounded PE/PB/market-cap/free-cash-flow style refs when normalized;
- explicit stale/fallback/proxy limitations.

Must not include:

- target-price or execution-ready claims from valuation evidence alone;
- broker/account payloads or recommendations.

### 4.4 News

Input source:

- `newsCatalysts.topNewsItems`
- `singleStockEvidencePacket.domains.news`

Allowed prompt content:

- top recent news item refs with `id`, title/summary, source tier, authority,
  published time, freshness, sentiment, relevance, and limitations;
- context-only fallback snippets only when clearly labeled `observationOnly` and
  `freshness=unknown`.

Must not include:

- article bodies;
- full `news_context`;
- raw URLs if the public report does not need them;
- copied provider payloads or stack traces.

### 4.5 Catalysts

Input source:

- `newsCatalysts.topCatalystItems`
- `singleStockEvidencePacket.domains.catalysts`

Allowed prompt content:

- catalyst refs with type, short summary, source authority, freshness, and
  limitations;
- missing-catalyst note when top lists are empty.

Must not include:

- unsupported material-event claims;
- long news prose duplicated from `news_context`;
- ungrounded supportive/negative catalyst language.

### 4.6 Sentiment

Input source:

- `newsCatalysts.sentimentSummary`
- `singleStockEvidencePacket.domains.sentiment`
- bounded item ids from news/catalyst refs

Allowed prompt content:

- aggregate sentiment direction only when backed by item refs or explicit
  observation-only context;
- confidence/freshness labels.

Must not include:

- social or news sentiment treated as score-grade evidence by default;
- "market consensus" claims without source authority.

### 4.7 Macro and sector context

Input source:

- `singleStockEvidencePacket.domains.macroLiquidity`
- `singleStockEvidencePacket.domains.sectorTheme`
- existing structured macro/sector fields only when already present

Allowed prompt content:

- short contextual notes with authority/freshness labels;
- missing/degraded notes when macro or sector evidence is unavailable.

Must not include:

- scanner, options, portfolio, or unrelated market-wide payloads;
- provider capability claims not actually wired into the Home runtime.

## 5. Prompt And Report Consumers

### 5.1 Prompt fields that should consume packet evidence

Future prompt assembly should consume the adapter in these locations:

- finance analysis instructions currently fed by `fundamental_context` and
  structured finance snippets;
- `fundamental_analysis`;
- `business_quality` / core thesis style fields, if present in the parsed model;
- `latest_news`;
- `risk_alerts`;
- `positive_catalysts`;
- `news_summary`;
- sentiment/catalyst narrative fields;
- data-insufficient and missing-evidence explanation text;
- no-advice/no-execution boundary statements.

The model should be instructed to cite evidence IDs for factual finance, news,
catalyst, sentiment, valuation, macro, and sector claims when those claims use
adapter evidence.

### 5.2 Report fields that should consume packet evidence

Future T-929 should map citation-safe evidence into:

- standard report fundamentals section;
- standard report earnings section;
- valuation highlights;
- news and catalyst highlights;
- sentiment summary;
- `reason_layer` / evidence-support explanation;
- public report missing-evidence disclosure;
- report/meta response mirrors for compatibility checks.

Report fields should render unavailable/degraded/blocked evidence explicitly
instead of fabricating citations or silently omitting missing domains.

### 5.3 Diagnostic-only fields

These fields must remain diagnostic-only and must not be used as public citation
evidence or direct LLM evidence text:

- execution logs and execution stages;
- provider attempts and full provider chains;
- data-source-router diagnostics;
- `_provider_meta` and raw provider result metadata;
- cache/router/env/internal labels;
- raw `context_snapshot` payloads;
- `decision_trace` internals;
- LLM attempt traces, response previews, and full prompt debug dumps;
- raw `news_context`;
- raw article bodies;
- stack traces and exception text;
- credentials, tokens, API keys, cookies, secrets, account identifiers, broker
  payloads, and session identifiers.

Sanitized high-level status derived from these fields may still inform
`missingEvidence`, `blockingReasons`, or `sourceSummary`.

## 6. Leakage Guardrails

Future adapter and report mapping tests should reject:

- raw provider payloads or copied JSON blobs;
- stack traces, Python exception internals, and request/router traces;
- cache keys, cache paths, environment names, model routing internals, and
  provider router labels not meant for consumers;
- credentials, tokens, cookies, API keys, account identifiers, broker payloads,
  or session identifiers;
- full prompt dumps, response previews, and LLM retry transcripts;
- full article bodies, scraped pages, or unbounded news text;
- buy/sell/order/trade/broker execution instructions or recommendations added
  by the new adapter/report sections;
- unsupported claims that evidence is ready, sufficient, high-confidence, or
  supportive when packet state is `insufficient`, `blocked`, `waiting`, or
  `observe_only`.

The adapter may include controlled limitation labels such as `observationOnly`,
`stale`, `fallback`, `providerTimeout`, or `unsupported`, but should map internal
reason codes to consumer-safe statements.

## 7. Prompt-Size And Token-Budget Guardrails

The adapter should be deterministic and aggressively bounded:

- include all domain summaries, but keep each domain note to one short line;
- cap financial refs to at most three per domain and eight total
  fundamentals/earnings/valuation refs;
- cap news refs to at most five `topNewsItems`;
- cap catalyst refs to at most three `topCatalystItems`;
- cap missing evidence notes to eight and next-evidence notes to five;
- cap titles to about 120 characters and summaries to about 160 characters;
- prefer evidence IDs over repeated source text;
- sort refs deterministically by domain priority, relevance/confidence, freshness
  timestamp, then ID;
- dedupe long text across `news_context`, `topNewsItems`, and
  `topCatalystItems`;
- never include full article text or full formatted intelligence reports;
- on integrity retry, reuse the same evidence index by ID instead of appending a
  second full copy of the evidence block.

If the adapter output exceeds its budget, trim lower-priority observation-only
items first while preserving missing/blocking notes and no-advice boundary text.

## 8. Future Test Requirements

### 8.1 T-928 Home LLM evidence input adapter

Required tests:

- ORCL-like partial evidence: US/HK `fundamental_context` unsupported, but
  supplemental finance refs exist; prompt adapter includes bounded
  `fundamentalsEarnings` refs and an explicit unsupported-context note.
- Unsupported US/HK `fundamental_context` with no supplemental refs: adapter
  emits insufficient/blocked finance notes and does not imply readiness.
- News timeout/fallback: adapter includes provider-timeout/missing-news notes,
  empty top lists, and no raw error/router text.
- Empty `top_positive_items` / `top_negative_items` / classified items: adapter
  emits missing news/catalyst/sentiment notes without fabricating items.
- Context-only news fallback: adapter emits bounded observation-only snippets,
  unknown freshness, and no article bodies.
- Prompt budget: output is deterministic, top-N capped, deduped, and stable
  across repeated runs.
- Leakage: prompt adapter output excludes raw provider payload markers, stack
  traces, secret-like strings, full prompt/debug text, and internal diagnostic
  labels.
- Consumer safety: adapter-added text does not add buy/sell/order/trade/broker
  recommendation language and does not use "ready", "sufficient", or
  "supportive" wording when packet state is degraded.

### 8.2 T-929 Home report citation-safe section mapping

Required tests:

- Report fundamentals, earnings, valuation, news, catalysts, and sentiment
  sections cite evidence IDs when evidence is used.
- Missing evidence renders explicit unavailable/degraded/blocked copy instead of
  fabricated citations.
- `singleStockEvidencePacket`, `fundamentalsEarnings`, and `newsCatalysts` remain
  compatible in top-level response, report, report meta, and details mirrors.
- Standard report payloads remain backward compatible for clients that do not
  yet render citations.
- Diagnostic-only fields are not rendered as citation sources.

### 8.3 T-930 prompt leakage regression tests

Required tests:

- Full assembled prompt excludes raw provider payloads, stack traces, full
  `news_context`, full article bodies, prompt dumps, credentials, broker/account
  payloads, and internal router/cache/env labels.
- Integrity retry does not duplicate long evidence blocks or leak previous
  response/debug content into public report fields.
- Packet `insufficient`, `blocked`, `waiting`, and `observe_only` states prevent
  hallucinated high-confidence or supportive evidence language.
- Response/report compatibility holds when packet evidence is absent, partial,
  or fully populated.

## 9. Proposed Write Task Sequence

### T-928 Home LLM evidence input adapter

Scope:

- Add a pure adapter that transforms existing packet-shaped data into
  `HomeLlmEvidenceInputV1`.
- Wire the adapter into the Home analyzer context before `_format_prompt()`.
- Add focused unit tests for ORCL-like partial input, unsupported
  `fundamental_context`, news timeout/fallback, empty top lists, budget caps, no
  leakage, and no hallucinated readiness.

Non-goals:

- no provider probing;
- no provider order/cache/runtime changes;
- no report renderer mapping;
- no frontend rendering.

### T-929 Home report citation-safe section mapping

Scope:

- Map citation-safe adapter/packet evidence into report sections.
- Preserve response/report/meta/details compatibility.
- Add tests for cited and missing-evidence rendering.

Non-goals:

- no new evidence acquisition;
- no prompt/model/routing change unless T-928 left an explicit adapter seam.

### T-930 prompt leakage regression tests

Scope:

- Add prompt/report leakage regression coverage across adapter, analyzer retry,
  and public report output.
- Assert no raw payloads, no prompt dumps, no internal diagnostics, no secrets,
  no article bodies, and no execution-grade trading copy in newly added sections.

Non-goals:

- no broad analyzer rewrite;
- no frontend redesign;
- no provider/runtime expansion.

## 10. Implementation Boundaries For Future Work

Keep the future write tasks additive and fail-closed:

- reuse current packet builders and normalizers;
- build prompt evidence from sanitized refs, not raw provider payloads;
- preserve existing endpoint and report fields unless explicitly scoped;
- keep `decision_trace`, execution logs, and router diagnostics out of citation
  inputs;
- do not change provider priority, timeout, cache, auth, storage, scanner,
  options, portfolio, config, CI, or lockfiles;
- keep consumer copy analytical and evidence-limited.

## Conclusion

The system now has the right response-side evidence packet, but the LLM still
sees legacy mixed context. T-928 should make packet evidence available to the
prompt as a bounded citation index. T-929 should map those citation IDs into
report sections. T-930 should lock the leakage and prompt-size guardrails so the
new citation path cannot expose raw runtime details or fabricate confidence.
