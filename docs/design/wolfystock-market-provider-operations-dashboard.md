# WolfyStock Market Provider Operations Dashboard

Date: 2026-05-06 Asia/Shanghai
Repository: `/Users/yehengli/daily_stock_analysis`
Branch: `main`
Mode: read-only design and architecture report; no product code, tests, CSS, backend/API, package/config, runtime behavior, provider behavior, cache behavior, migrations, endpoints, generated artifacts, or changelog changes.

## 1. Executive Summary

Recommended first dashboard scope: a read-only Admin operations surface that aggregates existing Market Overview provider metadata, existing `MarketCache` state, persisted market overview snapshots, and Admin Logs business events. It should answer: "Which market panels are live, stale, fallback, refreshing, slow, or failing, and where is the exact Admin Log evidence?"

Biggest operational value: reduce provider/API waste by showing fallback frequency, stale last-known-good age, cache/SWR state, slow cold starts, and repeated provider failures before operators add more refresh buttons, provider calls, or new sources. The dashboard should make existing degradation visible; it should not try to fix degradation in the same slice.

No-runtime-change confirmation: Phase 1 should be a read-only aggregation layer over existing metadata and logs. It must not change provider ordering, request frequency, SWR/cold-start timeout behavior, fallback factories, persistent snapshot semantics, Admin Logs retention, or Market Overview rendering.

Recommended route: `/zh/admin/market-providers`, not a subsection inside `/zh/settings/system`. Provider operations are audit/incident triage, not configuration editing. `/zh/settings/system` should remain personal/system control plane and config health; the provider operations route should drill through to Admin Logs and Market Overview without exposing raw config or secrets.

## 2. Current State Inventory

| Provider/source | Endpoint/service | Data type | Freshness/fallback metadata today | Cache/SWR behavior today | Current UI exposure | Gaps |
| --- | --- | --- | --- | --- | --- | --- |
| Yahoo Finance proxy / yfinance | `MarketOverviewService._latest_quote()`, `/api/v1/market-overview/indices`, `/volatility`, `/funds-flow`, `/macro`, `/api/v1/market/us-breadth` | US/global indices, volatility, ETF breadth, macro proxies, funds-flow proxy snapshots | `source`, `sourceLabel`, `sourceType`, `freshness`, `isFallback`, `isStale`, `delayMinutes`, item metadata, `providerHealth` | `MarketCache.get_or_refresh()` with TTL by cache key, stale return, background refresh, cold-start fallback after 2s, persistent snapshot fallback | Market Overview freshness badges and footer; Admin Logs entries when stale/fallback/failure/slow | No aggregated provider-level success rate, last-known-good age histogram, per-endpoint p50/p95 latency, or request volume view |
| Sina | `/api/v1/market/cn-indices`, `_fetch_sina_cn_index_quotes()` | CN/HK index snapshot | Item-level `asOf`, `source=sina`, `sourceLabel=新浪财经`, mixed/fallback card state when some fallback fillers remain | Same MarketCache/SWR path through `_classified_snapshot()` | Market Overview CN/HK cards show source/freshness; mixed state may appear as partial/fallback | No Sina-specific availability history or count of mixed cards by missing symbol |
| Binance spot/futures public APIs | `/api/v1/market/crypto`, `/crypto/stream`, `_fetch_crypto_market_snapshot()`, `_fetch_binance_kline_history()`, `_fetch_binance_funding_items()` | Crypto prices, trend, funding items | `source=binance`, `providerHealth`, item metadata, fallback static crypto snapshot with `isRefreshing` on cold fallback | Short crypto TTL, SWR, SSE stream seeded from realtime service or snapshot | Crypto Market Overview panel and stream status | No stream uptime metric, funding endpoint failure count, or separation between spot ticker, kline, and funding latency |
| CNN Fear & Greed | `/api/v1/market/sentiment`, `_fetch_cnn_fear_greed_snapshot()` | Fear & Greed history | `source=cnn`; if it fails, service attempts Alternative.me and keeps provider error in payload | MarketCache/SWR under sentiment TTL | Sentiment card shows provider/freshness | CNN failure is not separately charted from Alternative.me fallback success |
| Alternative.me | `/api/v1/market/sentiment`, `_fetch_alternative_fear_greed_snapshot()` | Fear & Greed fallback | `source=alternative_me` when CNN fallback succeeds | Same sentiment cache/SWR | Sentiment card source and Admin Logs if degradation is logged | Needs explicit "secondary provider used" count to diagnose CNN instability |
| Computed market temperature | `/api/v1/market/temperature`, `get_market_temperature()` | Composite scores from existing market panels | `reliableInputCount`, `fallbackInputCount`, `excludedInputCount`, `confidence`, `isReliable`, `fallbackUsed`, `providerHealth` | Uses existing panel getters, so it can reuse cached panel data but may trigger nested reads through the same service paths | Market Overview temperature surface | Needs dashboard to explain when computed outputs are degraded because inputs are fallback/stale |
| Market briefing | `/api/v1/market/market-briefing`, `get_market_briefing()` | Rule-based market briefing from existing inputs | Same trust counts as temperature plus briefing-specific warnings | Same cached input pattern | Market Overview briefing surface | Needs "computed from degraded inputs" rollup |
| Futures / CN short sentiment / CN breadth / CN flows / sector rotation / rates / FX commodities | `/api/v1/market/futures`, `/cn-short-sentiment`, `/cn-breadth`, `/cn-flows`, `/sector-rotation`, `/rates`, `/fx-commodities` | Market panels, many currently fallback/static or unavailable | `source=fallback`/`unavailable`, `fallbackUsed`, `isFallback`, `warning`, item metadata, `providerHealth` | MarketCache/SWR even for fallback factories | Market Overview cards mark fallback/unavailable honestly | Dashboard should separate "not connected by design" from "connected provider failed" |
| FMP | `data_provider/us_fundamentals_provider.py`, system provider validation | US fundamentals, quote/history/technical fallback outside Market Overview | Provider validation returns status/checks/duration; FMP data functions carry source fields | Separate provider/data-provider caching, not MarketCache | Settings/system provider validation; not Market Overview operations today | Include as "adjacent provider" only in later phases unless dashboard broadens beyond Market Overview |
| Akshare / Tushare / pytdx / baostock | `data_provider/base.py` fetcher routing and scanner/analysis paths | CN quote/history/universe providers | Data provider traces include provider attempts, reasons, failures in scanner/analysis diagnostics | Data-provider-specific caches and fallback, not MarketCache | Admin Logs/scanner diagnostics more than Market Overview | First dashboard should not merge these deeply with Market Overview unless fed by existing Admin Logs |
| Frankfurter | `src/services/fx_rate_service.py`, portfolio FX refresh | Portfolio FX rates | `provider`, `fetched_at`, `stale`, `cache_hit` surfaced in portfolio tests/API | Portfolio service cache/freshness path, not MarketCache | Portfolio FX panel, not Market Overview | Out of first slice unless provider dashboard becomes all-market-provider operations |
| Admin Logs | `ExecutionLogService.record_market_overview_fetch()`, `/api/v1/admin/logs` and `/sessions` | Business events and execution sessions | `category`, `event_name`, `provider`, `source`, `status`, `duration_ms`, `latency_ms`, `stale_age_minutes`, `fallbackUsed`, `isStale`, errors | Retention/storage governed by Admin Logs services | Admin Logs page, health summary, drilldown drawer | Needs provider-dashboard deep links and market-specific rollups |

## 3. Existing Observability

Admin Logs already have the right coarse seam. Market overview fetches call `record_market_overview_fetch()` and persist degraded or useful events while suppressing noisy success events. High-frequency successes such as cache hits, prewarm start/completion, and refresh start/completion are intentionally not default-visible unless slow, stale, fallback, or failed.

Existing event/category behavior:

| Signal | Current source | Notes |
| --- | --- | --- |
| Event categories | `market`, `cache`, `data_source`, `api`, plus broader Admin Logs categories | Market provider failures are normally `data_source`; stale served can be `market`; slow cold start can be `api`. |
| Event names | `MarketDataFallbackUsed`, `MarketDataStaleServed`, `MarketProviderRefreshFailed`, `MarketSnapshotServedStale`, `MarketCacheColdStartSlow` | Generated from provider log metadata and record logic; naming is not yet a single dashboard taxonomy. |
| Provider/source | `provider`, `source`, `target`, `raw_response.provider/source` | Useful but split across readable summary, event target, and raw response. |
| Request timing | `duration_ms`, `latency_ms`, frontend `durationMs` models | Per-fetch timing exists for market overview service calls; rollups do not yet expose p50/p95. |
| Cache state | `raw_response.cache` values such as `hit_or_refreshed`, `stale_refreshing`, `stale_or_fallback` | Useful but currently buried in Admin Logs detail/raw metadata. |
| Freshness state | `freshness`, `isFallback`, `isStale`, `isRefreshing`, `isFromSnapshot`, `lastSuccessfulAt`, `delayMinutes` | Strong panel/item metadata; no central operator rollup. |
| Storage/noise constraints | Admin Logs storage summary and retention cleanup | Dashboard should query small windows and aggregate; do not persist cache-hit spam. |

Provider failures today are observable when they produce a fallback/stale/failure event, but success volume and cache hit/miss volume are intentionally under-sampled to avoid log noise. The dashboard should respect this: live cards can read current cache metadata, while historical charts should use persisted degraded events and optional sampled rollups, not raw success spam.

## 4. Proposed Dashboard IA

Recommended route: `/zh/admin/market-providers`.

Why this route is better:

- The surface is operational triage and audit evidence, matching Admin Logs ownership.
- It avoids turning `/zh/settings/system` into a second admin console.
- It can link to `/zh/market-overview` for user-facing impact and `/zh/admin/logs` for evidence without editing provider config.
- It keeps dangerous/raw provider credentials out of the operator view.

Suggested sections:

| Section | Purpose | Primary data |
| --- | --- | --- |
| Provider health summary | Count live/cache/stale/fallback/partial/unavailable/error/refreshing states | Current provider status snapshot from existing panel metadata and cache entries |
| Live/fallback/stale counts | Immediate operational impact by panel/category | Current panel `providerHealth`, `freshness`, `fallbackUsed`, `isStale`, `isFromSnapshot` |
| Latency trend | Detect slow providers/cold starts before users see stale fallback | Admin Logs `durationMs`/`latency_ms` rollups by endpoint/provider |
| Last-known-good age | Show stale snapshot risk by panel | `lastSuccessfulAt`, `asOf`, persistent snapshot row timestamps, cache fetched/expires timestamps |
| Fallback frequency | Diagnose provider/API waste and unstable routes | Admin Logs `MarketDataFallbackUsed`, `MarketProviderRefreshFailed`, `MarketDataStaleServed` counts |
| Endpoint drilldown table | One row per market endpoint/card | Endpoint, card, provider, status, freshness, TTL, cache state, LKG age, latency, recent log link |
| Provider error recent log strip | Keep evidence close without dumping raw logs | Recent Admin Logs filtered to `category=data_source|market|cache` and market endpoints |
| Cache/SWR status | Explain whether users are seeing fresh, stale-refreshing, or fallback data | `MarketCacheEntry` metadata plus response `isRefreshing`/`lastError` |
| Data freshness heatmap | Fast scan of panel/item freshness by market domain | Item-level metadata from current panel snapshots |
| Manual smoke actions if safe | Phase-later explicit operator checks | Only safe, rate-limited, confirmable probes that reuse existing validation semantics; not first slice |

Default filter set should be Chinese-first:

- 时间窗口: 最近 15 分钟 / 1 小时 / 24 小时 / 7 天
- 状态: 全部 / 实时 / 缓存 / 过期 / 备用 / 部分数据 / 暂不可用 / 数据异常
- 数据域: 全球指数 / A股港股 / 加密货币 / 宏观利率 / 汇率商品 / 情绪 / 资金流
- 证据级别: 降级事件 / 失败事件 / 慢请求 / 全部事件

## 5. UI Design Requirements

The dashboard must follow the WolfyStock deep-space quant-terminal constitution:

- Use ghost-glass surfaces, thin borders, restrained glow, and dense data-first hierarchy.
- Use Chinese labels for UI chrome: `数据源健康`, `备用频率`, `最近成功快照`, `过期面板`, `Admin Logs 证据`.
- Keep provider names, tickers, endpoint paths, metrics, and currencies in domain-standard English where appropriate.
- Reuse canonical primitives: `GlassCard`, `SectionShell` or equivalent route shell, common buttons, status/display helpers, `DataFreshnessBadge`/market-owned freshness semantics, and Admin Logs drawer/table patterns.
- No raw tokens, URLs with secrets, API keys, credential values, config dumps, or raw provider payloads in primary UI.
- Developer details must be collapsed by default and sanitized.
- Do not use native-looking controls; use existing ghost controls and fixed-size icon buttons.
- Mobile layout should become a scan-first sequence: summary strip, status counts, endpoint table cards, recent evidence strip. Tables should collapse into row cards with stable labels and no horizontal overflow.
- Do not add decorative marketing hero sections; this is an operator dashboard, not a landing page.

Recommended cards/tables/charts:

| UI element | Label | Design notes |
| --- | --- | --- |
| Summary metric row | `实时`, `缓存`, `过期`, `备用`, `部分数据`, `异常` | Compact metric cards, not large hero cards. |
| Provider status matrix | `数据源状态矩阵` | Rows by provider/source, columns by status/count/last failure/LKG age. |
| Endpoint drilldown table | `端点健康明细` | Endpoint, card, provider, freshness, SWR, TTL, latency, fallback count, log link. |
| Latency line chart | `延迟趋势` | Use Admin Logs rollups; avoid live provider calls. |
| Fallback stacked bars | `备用/过期频率` | Split fallback, stale, partial, unavailable. |
| LKG age heatmap | `最近成功快照年龄` | Color by age buckets; click row opens evidence. |
| Recent log strip | `最近降级事件` | Link to Admin Logs detail drawer; no raw payload by default. |
| Cache/SWR panel | `缓存与刷新状态` | Show TTL, expires in, refreshing, stale served, last error. |

## 6. Data Model / API Sketch

Docs-only sketch; no migration or endpoint is approved here.

### Provider status snapshot

Read-only, current-state response derived from current cache and market panel metadata:

```json
{
  "generatedAt": "2026-05-06T12:00:00+08:00",
  "window": "24h",
  "items": [
    {
      "provider": "sina",
      "sourceLabel": "新浪财经",
      "sourceType": "public_proxy",
      "domain": "cn_indices",
      "endpoint": "/api/v1/market/cn-indices",
      "card": "ChinaIndicesCard",
      "status": "partial",
      "freshness": "cached",
      "asOf": "2026-05-06T11:30:00+08:00",
      "updatedAt": "2026-05-06T11:31:00+08:00",
      "lastSuccessfulAt": "2026-05-06T11:30:00+08:00",
      "lastKnownGoodAgeMinutes": 30,
      "latencyMs": 184,
      "isFallback": false,
      "isStale": false,
      "isRefreshing": false,
      "isFromSnapshot": false,
      "fallbackUsed": true,
      "warning": "部分数据为备用或旧快照"
    }
  ]
}
```

Historical note: older service-local payloads or logs may still emit legacy `sourceType` values such as `public_api`; new design examples in this document use the registry vocabulary (`public_proxy`, `unofficial_proxy`, `official_public`, etc.).

### Provider event rollup

Historical rollup from Admin Logs, grouped by provider/source/card/endpoint:

```json
{
  "window": "24h",
  "items": [
    {
      "provider": "binance",
      "endpoint": "/api/v1/market/crypto",
      "eventCount": 12,
      "failureCount": 2,
      "fallbackCount": 1,
      "staleServedCount": 3,
      "slowCount": 1,
      "failureRate": 0.1667,
      "topReasons": ["timeout", "provider_error"],
      "latestLogEventId": "..."
    }
  ]
}
```

### Endpoint timing rollup

Use existing `duration_ms`/`latency_ms`; do not add provider calls:

```json
{
  "endpoint": "/api/v1/market/sentiment",
  "provider": "cnn",
  "sampleCount": 18,
  "p50LatencyMs": 420,
  "p95LatencyMs": 2100,
  "maxLatencyMs": 2500,
  "slowThresholdMs": 2000
}
```

### Cache status rollup

Read `MarketCache` state and persistent snapshot metadata without mutation:

```json
{
  "cacheKey": "crypto",
  "ttlSeconds": 15,
  "fetchedAt": "2026-05-06T12:00:00+08:00",
  "expiresAt": "2026-05-06T12:00:15+08:00",
  "isFresh": true,
  "isRefreshing": false,
  "lastError": null,
  "persistentSnapshotAvailable": true,
  "persistentSnapshotAgeMinutes": 4
}
```

### Admin log drill-through link model

Each dashboard row should carry a structured Admin Logs query rather than raw SQL or raw payload:

```json
{
  "label": "查看 Admin Logs",
  "route": "/zh/admin/logs",
  "query": {
    "category": "data_source",
    "provider": "sina",
    "query": "/api/v1/market/cn-indices",
    "since": "24h"
  },
  "eventId": "optional-session-or-business-event-id"
}
```

## 7. Which Data Is Real-Time, Cached, Aggregated, Or Historical

| Data | Treatment | Reason |
| --- | --- | --- |
| Current provider/card status | Real-time from existing in-process cache and latest panel metadata | Needed for operator snapshot; must not call providers just to populate the page. |
| Current item freshness/fallback | Real-time from current panel payloads already served to Market Overview | Mirrors user-facing trust state. |
| Cache TTL/expires/refreshing/last error | Real-time from `MarketCache` metadata | Explains SWR and stale-refreshing states. |
| Last-known-good age | Cached/current from persistent snapshot and payload timestamps | Critical for stale risk; no extra provider calls. |
| Latency p50/p95 and slow counts | Aggregated from Admin Logs over selected window | Avoid log spam and expensive live probes. |
| Fallback/stale/failure frequency | Aggregated from Admin Logs | Historical diagnosis and waste reduction. |
| Recent provider errors | Historical list from Admin Logs | Evidence and drill-through. |
| Provider credential readiness | Cached/settings-derived only if later integrated | Do not expose secrets; do not probe in first slice. |
| Manual smoke result | Historical only after explicit safe probe phase | Out of Phase 1 to avoid provider/API waste. |

## 8. Metrics To Reduce Provider/API Waste And Diagnose Fallback

- Fallback frequency by endpoint/provider over 15m/1h/24h/7d.
- Stale-served count and average stale age by card.
- Last-known-good age buckets: `<5m`, `5-30m`, `30-120m`, `>120m`, `none`.
- Slow cold-start count and p95 latency by endpoint.
- Cache state distribution: fresh cache, stale-refreshing, stale-or-fallback, persistent snapshot, static fallback.
- Repeated failure reason counts: timeout, provider_error, rate_limited, empty_result, invalid_response, unauthorized.
- Secondary provider usage: CNN failed but Alternative.me succeeded; yfinance proxy fallback; mixed Sina/fallback CN rows.
- Fallback-only/not-connected panels, separated from provider failure panels.
- User-impact estimate: number of Market Overview cards and items currently fallback/stale.
- Suppressed-success ratio should remain approximate or sampled only; do not persist every cache hit to calculate it.

## 9. Safety And Non-Goals

First implementation must explicitly avoid:

- Changing provider behavior, provider priority, provider timeouts, or provider fallback order.
- Auto-refreshing aggressively or adding new polling loops.
- Calling external providers just to populate the dashboard.
- Exposing secrets, raw tokens, raw provider URLs with credentials, or raw config values.
- Manually mutating/clearing cache in the first slice.
- Adding notification routing, alert thresholds, or incident escalation in the first slice.
- Adding database migrations in Phase 1.
- Adding new market data endpoints in this report task.
- Treating fallback/static placeholder panels as real market data.
- Hiding fallback/stale/mock states behind generic "healthy" labels.
- Combining this dashboard with Market Overview redesign or Settings refactor work.

## 10. Implementation Roadmap

| Phase | Scope | Likely files | Tests | Playwright/browser verification | Risks | Parallel safety |
| --- | --- | --- | --- | --- | --- | --- |
| Phase 0 | This report/design only | `docs/design/wolfystock-market-provider-operations-dashboard.md` | `git diff --check`; optional markdown lint if available | Not required, docs-only | Report drift if not tied to current code | Single docs file; safe with parallel product work |
| Phase 1 | Read-only backend aggregation from existing logs/cache metadata | New service near `src/services/market_overview_service.py` or `src/services/market_provider_operations_service.py`; existing Admin Logs service only by read calls | Unit tests for aggregation without provider calls; tests that provider fetchers are not invoked | API smoke only if endpoint added in that future task | Accidentally triggering provider fetches; log query cost; in-process cache visibility in multi-worker deploys | Backend/API only; no frontend/CSS |
| Phase 2 | Frontend dashboard shell | `apps/dsa-web/src/pages/*`, route/nav config, API client types, existing common/market/admin primitives | Page tests with mocked aggregation payload; design guard, lint, build | Desktop and 390px route checks; Admin Logs drill-through route check | Route-local primitive drift; mobile table overflow; raw details leakage | Frontend-only; do not edit provider code |
| Phase 3 | Historical rollups | Admin Logs aggregation helpers or materialized read model if reviewed | Rollup tests for window/grouping and storage limits | Dashboard chart/table checks | Storage/noise pressure; migration may be proposed but must be separately reviewed | Serialize with Admin Logs retention/storage work |
| Phase 4 | Alert thresholds / notification integration | Notification rules and provider operations config after review | Notification dry-run tests, threshold tests | Admin notification flow checks | Alert fatigue, secret leakage, false positives | Separate task; do not combine with dashboard build |

## 11. Recommended First Implementation Task

Prompt title: `Implement read-only Market Provider Operations aggregation API from existing cache and Admin Logs`

Scope: backend-only, no provider behavior changes. Add a service that aggregates existing `MarketCache` metadata, persistent market overview snapshots, and Admin Logs degraded-market events into a read-only status response. Tests must prove the aggregator does not call external providers, does not mutate cache, and returns provider/card/endpoint status, LKG age, fallback/stale counts, and Admin Logs drill-through query fields.

## 12. Appendix: Commands And Files Inspected

Preflight commands:

```bash
cd /Users/yehengli/daily_stock_analysis
pwd
git branch --show-current
git status --short
git status --branch --short
git log --oneline -180
./scripts/task_preflight.sh || true
```

Static investigation:

```bash
rg -n "MarketCache|market_cache|provider|freshness|fallback|stale|last-known|last_known|isRefreshing|isFallback|provider_health|latency|duration|timing|SWR|cache|prewarm|market-overview|market overview|cn-indices|crypto|sentiment|volatility|macro|funds-flow|rates|fx|commodities|futures|briefing|AdminLogs|admin logs|execution_log|log event|category|event_name" src api apps/dsa-web/src tests docs | head -1200
rg --files docs | rg -i "admin|execution|log|market|provider|freshness|fallback|overview|cache" | sort
rg --files src/services api/v1/endpoints api/v1/schemas apps/dsa-web/src | rg -i "market|provider|admin|execution|log|cache|freshness|portfolio|fx|crypto" | sort
rg -n "class MarketCache|def get_or_refresh|cold_start|isRefreshing|fallback|stale|freshness|last_known|last-known|duration|latency|prewarm|record_.*market|ExecutionLog|event_name|category|provider|durationMs|cacheHit" src/services api/v1/endpoints api/v1/schemas apps/dsa-web/src/api apps/dsa-web/src/pages apps/dsa-web/src/components/market-overview tests | head -1000
rg -n "def _provider_health|def _provider_log_meta|def _with_market_meta|def _with_item_meta|record_market_overview_fetch|list_business_events|summarize_business_events|providerHealth|fallbackUsed|lastSuccessfulAt|isFromSnapshot" src/services/market_overview_service.py src/services/execution_log_service.py apps/dsa-web/src/pages/MarketOverviewPage.tsx apps/dsa-web/src/components/market-overview apps/dsa-web/src/api/market.ts apps/dsa-web/src/api/marketOverview.ts apps/dsa-web/src/pages/AdminLogsPage.tsx apps/dsa-web/src/api/adminLogs.ts tests | head -900
rg -n "requests\\.get|yfinance|yf\\.|sina|binance|cnn|alternative|fear|FMP|fmp|tushare|akshare|pytdx|baostock|eastmoney|Yahoo|frankfurter|premiumIndex|finance.yahoo|query1.finance|query2.finance" src/services/market_overview_service.py src/services/fx_rate_service.py data_provider src/services | head -700
rg -n "market_overview_snapshot|save_market_overview_snapshot|get_market_overview_snapshot|execution_log_sessions|execution_log_events|business_event|provider|duration_ms|latency" src/storage.py src -g'*.py' | head -800
```

Required docs inspected:

- `CODEX_FRONTEND_DESIGN_CONSTITUTION.md`
- `docs/design/wolfystock-canonical-ui-primitives.md`
- `docs/audits/wolfystock-frontend-design-conformance-audit.md`
- `docs/qa/wolfystock-workflow-qa-pass.md`
- `docs/operations/parallel-codex-playbook.md`
- `docs/audits/wolfystock-css-cleanup-closure-report.md`

Code/docs files inspected:

- `src/services/market_cache.py`
- `src/services/market_overview_service.py`
- `src/services/execution_log_service.py`
- `src/services/admin_logs_service.py`
- `src/services/fx_rate_service.py`
- `src/services/market_scanner_service.py`
- `src/storage.py`
- `api/v1/endpoints/market.py`
- `api/v1/endpoints/market_overview.py`
- `api/v1/endpoints/admin_logs.py`
- `api/v1/schemas/admin_logs.py`
- `apps/dsa-web/src/api/market.ts`
- `apps/dsa-web/src/api/marketOverview.ts`
- `apps/dsa-web/src/api/adminLogs.ts`
- `apps/dsa-web/src/pages/MarketOverviewPage.tsx`
- `apps/dsa-web/src/components/market-overview/marketOverviewPrimitives.tsx`
- `apps/dsa-web/src/pages/AdminLogsPage.tsx`
- `tests/test_market_overview_snapshot.py`
- `tests/test_market_overview_depth.py`
- `tests/api/test_market_freshness.py`
- `tests/api/test_market_crypto.py`
- `tests/api/test_market_sentiment.py`
- `tests/api/test_admin_logs.py`
- `tests/test_execution_log_service.py`
- `tests/api/test_logging.py`

Baseline checks:

```bash
cd /Users/yehengli/daily_stock_analysis/apps/dsa-web
npm run check:design
npm run lint
npm run build

cd /Users/yehengli/daily_stock_analysis
python3 -m compileall -q src api
```

Observed baseline results before report creation:

- `npm run check:design`: PASS, 216 files scanned, 0 blocking violations, 0 warnings.
- `npm run lint`: PASS, `eslint .` exited 0.
- `npm run build`: FAIL before this docs file was created; `apps/dsa-web/src/i18n/core.ts` has duplicate object literal keys at lines 805 and 3685.
- `python3 -m compileall -q src api`: PASS.
- Full `./scripts/ci_gate.sh`: not run. This is a docs-only report and the requested frontend build baseline is already blocked by an existing product-code TypeScript error outside this task's editable scope.

Markdown lint:

- No runnable markdown lint script was found. Static search only found prior docs mentioning markdown lint status, and no root package script or web package script for markdown lint.
