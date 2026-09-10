# Historical Market Data Foundation v1

> Status: Canonical domain contract
> Scope: normalized historical OHLCV rows, quality outcomes, persistence, and read interfaces
> Operations: [`docs/operations/historical-ohlcv-seed.md`](../operations/historical-ohlcv-seed.md)

WolfyStock historical market-data consumers should use the canonical foundation
contract instead of provider-shaped payloads. The boundary is:

```text
Raw provider observation
-> adapter/normalizer
-> CanonicalHistoricalBar
-> HistoricalBarQualityOutcome
-> HistoricalMarketDataRepository
-> HistoricalMarketDataFoundation read methods
-> product integration contract
```

## Canonical Bar

`src.services.historical_market_data_foundation.CanonicalHistoricalBar` is the
canonical internal bar model. It carries market and venue identity, canonical
symbol, provider symbol, interval, session date, optional timestamp, market
timezone, OHLCV values, adjustment metadata, currency, provider/source,
observation/as-of metadata, ingestion id, lineage id, normalization version,
and quality state.

For US ticker-only symbols, `venue = UNRESOLVED` is canonical identity state;
`MARKET_EXCHANGE["us"] = XNYS` remains a trading-calendar lookup only.

Provider-specific field names such as `Adj Close`, `Date`, `开盘`, or `成交量`
must stay inside `normalize_provider_historical_bars`. Product read consumers
must not depend on those raw field names.

`observedAt`/`observed_at` records when WolfyStock or a provider observed the
payload. It is lineage metadata, not a market-data cutoff. `asOf`/`as_of` is
accepted only when the source supplies an explicit data cutoff; missing cutoff
evidence remains missing and is never filled from observation or retrieval
time. The foundation preserves both fields independently.

## Quality Outcomes

`HistoricalBarQualityOutcome` produces three product-facing states:

- `usable`: product-readable and no quality reason codes.
- `degraded`: product-readable with reason codes such as `missing_session_gap`
  or `source_metadata_gap`; no missing bars are fabricated.
- `rejected`: not product-readable for invalid identity, malformed timestamp,
  invalid OHLC, negative values, non-monotonic ordering, or conflicting
  duplicate bars.

Quality validation is deterministic and does not repair, interpolate, or
fabricate historical market data.

## Development Local Replay

`WOLFYSTOCK_DEVELOPMENT_DATA_MANIFEST` 是显式 opt-in 的本地 historical
replay 输入。它只接受一个 manifest 文件；其中每个 payload 必须是 manifest
目录下的相对 JSON 路径，并以 SHA-256 绑定。manifest、entry 和 payload 的
market、canonical symbol、source、provider、`observedAt`、`asOf`、interval
和 non-production 标记必须一致，否则 replay fail closed。

replay 复用本合同的 canonical identity、质量和 persistence owner，供已接入
的 Scanner 与 Backtest consumer seam 读取。它不改变现有 local US parquet
优先级，也不启用 provider network path。每项 replay observation 都必须保留：

- `delivery=local_replay`、`historical=true`、`replay=true`、`development=true`；
- `authority=false`、`fallback=false`、`productionEligible=false`、`observationOnly=true`；
- `freshness=stale`，因为 historical replay 不能表示 current 或 live 市场状态。

每项 observation 的 `observedAt` 必须是有时区的采集时间。`asOfState=known`
时，`asOf` 必须是来源明确提供的、带时区的数据 cutoff；`asOfState=unknown` 时，
`asOf` 必须为 `null`。采集时间、请求时间或最后一根 bar 的日期都不得被填成 source
cutoff。manifest entry 与 payload 必须逐字保留相同的 as-of 状态和值。

该输入机制不是随仓数据集，也不证明任一市场有可分发或可用的真实数据。不得使用
synthetic/R06 fixture、fabricated price、缺失 hash 的 payload，或把 replay 用作
DATA-001、REL-001、production provider、实时 market context、portfolio valuation
或免费网络 provider qualification 的证据。

## Scanner Historical Research Seam

`us_historical_research_v1` 是 Scanner 的显式历史开发 profile。调用
`POST /api/v1/scanner/run` 时必须同时传入：

- `evaluation_mode=historical_development`；
- `evaluation_cutoff`，表示包含当日的已完成交易日截止日期。

该 profile 只接受 verified development replay（或等价的显式本地历史数据平面），并将
截止日期传给历史 OHLCV 读取边界；cutoff 之后的 bar 不得参与候选或 benchmark 计算。
运行和 readback 会保留 `evaluationMode`、`evaluationCutoff` 与 profile identity，供
Research Radar 及 owner-scoped Watchlist 继续传递。

历史候选可以在自己的 cutoff-bound information set 内进行 factor eligibility 和
ranking，但其来源仍是 `freshness=stale`、`observationOnly=true`、
`productionEligible=false`、`authority=false`；它不是 current、live 或
decision-grade signal。Watchlist 的 `scanner_lineage_v1` 保留
`evaluation_mode`、`evaluation_cutoff` 和 `historical_research=true`，同时继续执行
原有的 owner scope 与 no-advice 边界。

Scanner 候选进入单股 Research 时，路由只携带持久化 `scannerRunId` 作为 lookup
pointer；Research 必须通过既有 owner-scoped Scanner run readback 重新读取证据，并将
canonical symbol、market、完成状态、历史模式和 cutoff 与候选逐项匹配。URL 中的
symbol、market 或 source 不构成 evidence authority。匹配成功后，Research 可以单独
展示该 run 已持久化的 cutoff 与历史就绪度；current quote、consumer history 和 chart
仍由 `/stocks/*` 合同独立决定，不得由 development replay 补齐。缺失、不可访问、
格式错误或身份不匹配的 lineage 一律不展示 Scanner 历史证据，也不得回退到其他 run。

## Persistence

`src.repositories.historical_market_data_repo.HistoricalMarketDataRepository`
owns the idempotent persistence boundary for this foundation. Its natural key is:

```text
market + venue + canonical_symbol + asset_type + interval + session_date + provider + adjustment_status
```

Repeated ingestion of the same logical observation is counted as a duplicate.
Conflicting re-ingestion is rejected and preserves the existing canonical bar.
The repository creates narrowly scoped SQLite tables for isolated tests and
future migration wiring; this task does not run a production backfill or write
production data.

## Read Interface

`HistoricalMarketDataFoundation` exposes stable application-facing reads:

- `query_bars(symbol, market, interval, start, end)`
- `latest_bar(symbol, market, interval)`
- `coverage_range(symbol, market, interval)`
- `freshness_summary(symbol, market, interval)`
- `provenance_summary(symbol, market, interval)`

The returned objects and summaries expose canonical identity, coverage,
freshness, quality, provider/source provenance, as-of metadata, and
normalization lineage without leaking provider raw payload shapes.

The foundation does not own an interval- or market-specific age threshold, so
an explicit cutoff alone does not justify a `fresh` claim. Its freshness
summary reports `unknown` until a policy-bearing consumer supplies the relevant
freshness context; quality/readability remains independently represented.

## Product Seams

- Scanner can request `coverage_range` and `freshness_summary` before treating
  historical coverage as available for candidate workflows.
- Stock Research can request `query_bars` plus `provenance_summary` to build
  price-history evidence without understanding provider-specific rows.
- Backtest can request deterministic `query_bars` ranges and reject execution
  when quality or coverage summaries are not acceptable for the chosen run.

This is an integration contract only. It does not wire Scanner, Stock Research,
or Backtest runtime behavior to the new foundation, and it does not alter
provider priority, fallback, source-authority, scoring, fill, cost, portfolio,
or auth semantics.
