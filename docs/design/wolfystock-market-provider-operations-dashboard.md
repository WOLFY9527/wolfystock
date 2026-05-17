# WolfyStock Market Provider Operations Dashboard

Status: Linear OS aligned replacement for the older provider-operations design note.
Repository: `/Users/yehengli/daily_stock_analysis`
Intended path: `docs/design/wolfystock-market-provider-operations-dashboard.md`

## 1. Purpose

This document is useful and should be kept.

It defines a future read-only Admin/Ops surface for market-provider health. The dashboard should aggregate existing Market Overview provider metadata, `MarketCache` state, persisted market-overview snapshots, and Admin Logs business events. Its job is to answer:

```text
Which market panels are live, cached, stale, fallback, refreshing, slow, unavailable, or failing — and where is the exact Admin Logs evidence?
```

The document must not be used as a visual-design source for the normal product pages. Its target surface is an `OpsConsole`, not Home, Scanner, Watchlist, Portfolio, or Options Lab.

## 2. Linear OS Alignment

Use the current WolfyStock Linear OS design language:

- charcoal app canvas, not pure-black page islands;
- slim product shell inherited from the app shell;
- one dominant operations console surface;
- table/row/matrix first, not metric-card sprawl;
- compact filters and status strips;
- compact Admin Logs drill-through;
- raw diagnostics collapsed by default;
- no decorative material effects as routine hierarchy;
- no product-route admin/backend visual leakage.

Read with:

```text
docs/codex/WOLFYSTOCK_LINEAR_OS_DESIGN_LANGUAGE.md
docs/codex/WOLFYSTOCK_FRONTEND_SURFACE_USAGE.md
docs/codex/WOLFYSTOCK_FRONTEND_ROUTE_TEMPLATES.md
docs/codex/CODEX_FRONTEND_DESIGN_CONSTITUTION.md
docs/codex/WOLFYSTOCK_PROVIDER_BUDGET_AND_ROUTING_RULES.md
docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md
```

## 3. Route And Ownership

Recommended route:

```text
/zh/admin/market-providers
```

Rationale:

- provider operations is incident/audit triage, not user settings;
- it should live with Admin Logs and operator workflows;
- it should drill through to Admin Logs evidence;
- it should not expose credentials, raw configs, secrets, or provider payloads;
- it should not change provider behavior.

Canonical surface:

```text
OpsConsole
```

This route may be denser than product pages, but it must still use the Linear OS shell, row density, surface ladder, and disclosure discipline.

## 4. First-Slice Scope

The first implementation should be read-only.

Allowed:

- aggregate current panel metadata already exposed by Market Overview services;
- read `MarketCache` metadata without mutation;
- read persisted market overview snapshots;
- aggregate Admin Logs degraded-market events;
- produce drill-through query objects for Admin Logs;
- expose status rows, timing summaries, and last-known-good age.

Forbidden in the first slice:

- changing provider ordering;
- changing provider timeout/fallback behavior;
- changing `MarketCache` TTL/SWR/cold-start behavior;
- calling external providers just to populate this dashboard;
- adding aggressive polling;
- mutating or clearing cache;
- adding notification routing or alert thresholds;
- adding database migrations without a separate reviewed task;
- exposing raw credentials, secrets, request headers, raw provider URLs, or raw provider payloads.

## 5. Data Sources

| Source | Use | Notes |
| --- | --- | --- |
| Market Overview panel metadata | current user-impact state | freshness, fallback, stale, provider health, item metadata |
| `MarketCache` metadata | cache/SWR state | TTL, refreshing, last error, stale served |
| persisted snapshots | last-known-good age | snapshot availability and age buckets |
| Admin Logs business events | historical degradation evidence | fallback, stale served, provider failures, slow cold starts |
| provider configuration health | later phase only | no secrets; no live probes in first slice |

## 6. Information Architecture

Default layout:

1. Command/filter strip
   - 时间窗口
   - 状态
   - 数据域
   - 证据级别
2. Health summary strip
   - 实时
   - 缓存
   - 过期
   - 备用
   - 部分数据
   - 异常
3. Provider status matrix
   - provider/source rows
   - domain, status, last success, last failure, fallback count
4. Endpoint drilldown table
   - endpoint, card/panel, provider, freshness, cache state, TTL, latency, fallback count, log link
5. Last-known-good age table or heat band
   - `<5m`, `5-30m`, `30-120m`, `>120m`, `none`
6. Recent degraded event strip
   - links into Admin Logs
7. Collapsed diagnostics
   - sanitized raw event summaries only when explicitly opened

Avoid:

- a grid of unrelated summary blocks;
- large hero panels;
- repeated empty modules;
- raw provider or cache objects in the first viewport.

## 7. UI Requirements

Use `components/linear` or existing Linear-compatible adapters.

Preferred primitives:

```text
DataWorkbenchFrame
ConsoleStatusStrip
DenseRows
ConsoleDisclosure
ConsoleContextRail when selected detail is useful
WolfyCommandBar for filters/search
```

Operator labels should be Chinese-first:

```text
数据源健康
备用频率
最近成功快照
过期面板
缓存状态
刷新状态
最近降级事件
查看 Admin Logs
```

Provider names, endpoint paths, metrics, currencies, and domain codes may remain in English when they are domain-standard.

Rows should contain concrete operational evidence:

- provider/source
- endpoint
- freshness
- fallback/stale state
- last-known-good age
- latency p50/p95 when available
- recent failure count
- Admin Logs drill-through link

Do not use UI copy that says the dashboard is trustworthy, readable, summarized, ready, or useful. Show evidence instead.

## 8. Data Classification

| Data | Treatment | Reason |
| --- | --- | --- |
| Current provider/panel status | current state from existing metadata | mirrors user-facing market data trust |
| Cache TTL/expires/refreshing | current state from cache metadata | explains SWR behavior |
| Last-known-good age | cached/current from snapshots and timestamps | indicates stale risk |
| Latency p50/p95 | aggregated from Admin Logs | avoids live provider calls |
| Fallback/stale/failure frequency | aggregated from Admin Logs | diagnosis without log spam |
| Recent provider errors | historical event list | evidence and drill-through |
| Provider credential readiness | later phase only | avoid secrets and live probes |
| Manual smoke results | later phase only | avoid API waste |

## 9. API Shape Sketch

This is design-only; no endpoint is approved by this document.

```json
{
  "generatedAt": "2026-05-06T12:00:00+08:00",
  "window": "24h",
  "summary": {
    "live": 8,
    "cached": 12,
    "stale": 3,
    "fallback": 4,
    "partial": 2,
    "error": 1
  },
  "items": [
    {
      "provider": "sina",
      "sourceLabel": "新浪财经",
      "domain": "cn_indices",
      "endpoint": "/api/v1/market/cn-indices",
      "panel": "China indices",
      "status": "partial",
      "freshness": "cached",
      "lastKnownGoodAgeMinutes": 30,
      "latencyMs": 184,
      "isFallback": false,
      "isStale": false,
      "isRefreshing": false,
      "adminLogsLink": {
        "route": "/zh/admin/logs",
        "query": {
          "category": "data_source",
          "provider": "sina",
          "query": "/api/v1/market/cn-indices",
          "since": "24h"
        }
      }
    }
  ]
}
```

## 10. Metrics

Useful provider-waste and fallback diagnostics:

- fallback frequency by endpoint/provider over 15m/1h/24h/7d;
- stale-served count and average stale age by panel;
- last-known-good age buckets;
- slow cold-start count and p95 latency by endpoint;
- cache state distribution;
- repeated failure reason counts;
- secondary provider usage;
- fallback-only/not-connected panels separated from provider failures;
- user-impact estimate: affected panels/items.

Do not persist every cache hit only to calculate a success ratio. Prefer bounded event rollups and current-state metadata.

## 11. Implementation Roadmap

| Phase | Scope | Risk | Parallel safety |
| --- | --- | --- | --- |
| Phase 0 | this design document only | low | safe with product work |
| Phase 1 | read-only backend aggregation from existing logs/cache metadata | medium | backend/API only, no provider behavior |
| Phase 2 | frontend `OpsConsole` route | medium | frontend-only, after API contract is stable |
| Phase 3 | historical rollups | medium/high | serialize with Admin Logs storage work |
| Phase 4 | alert thresholds / notification integration | high | separate task only |

Recommended first implementation task:

```text
Implement read-only Market Provider Operations aggregation API from existing cache and Admin Logs.
```

Scope: backend-only. Tests must prove the aggregator does not call external providers, does not mutate cache, and does not change provider ordering/fallback behavior.

## 12. Validation Expectations

Docs-only changes:

```bash
git diff --check -- docs/design/wolfystock-market-provider-operations-dashboard.md
bash scripts/release_secret_scan.sh
```

Future backend aggregation:

```bash
python3 -m py_compile <changed python files>
python3 -m pytest -q <focused aggregation/admin log tests>
git diff --check
bash scripts/release_secret_scan.sh
```

Future frontend route:

```bash
npm --prefix apps/dsa-web run test -- <focused admin/provider route tests>
npm --prefix apps/dsa-web run build
npm --prefix apps/dsa-web run check:design
python3 scripts/check_frontend_design_constitution.py
git diff --check
bash scripts/release_secret_scan.sh
```

Browser proof for the route must include `1440x1000` and `390x844`.
