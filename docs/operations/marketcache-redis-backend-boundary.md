# MarketCache Redis Backend Boundary

Status: mirror-policy boundary only. A real Redis/Valkey adapter is deferred, not implemented, and not enabled.

## Current remote seam

- `MarketCache` currently exposes only a best-effort remote mirror seam behind `MarketCacheRemoteBackend`.
- The default backend remains `NullMarketCacheRemoteBackend`, so current behavior stays local-only unless a caller injects a test double.
- The seam is mirror-only: current runtime may project a JSON-safe document for persistence, but it does not read, hydrate, or re-authorize payloads from any remote store.
- No Redis/Valkey package, import, env flag, config flag, or runtime enablement is required in the current implementation.

## Current MarketCache semantics to preserve

- TTL remains per cache key/category.
- Stale-while-revalidate remains the default stale path: expired entries may be served as stale while a background refresh runs.
- Cold-start de-duplication remains process-local: concurrent cold requests for one key coalesce to one fetch attempt in the current process.
- Per-key locking remains process-local via in-memory locks; it is not a distributed lock.
- Fallback and stale retention remain allowed: timeout/error paths may return fallback payloads or the last safe stale payload without relabeling them as live.
- Background refresh remains asynchronous `Future`-based runtime behavior; stale/cold fallback responses may carry `isRefreshing=true` while refresh continues.
- Freshness and fallback metadata must remain preserved in payloads, including labels such as `freshness`, `isFallback`, `isStale`, `isPartial`, `isSynthetic`, `isRefreshing`, `lastError`, `source`, `sourceLabel`, `asOf`, `updatedAt`, `providerHealth`, `evidenceSnapshot`, `sourceConfidence`, and `scoreReliabilityAllowed`.

## T-641 JSON-safe serialization contract

- Remote storage may persist only a JSON-safe projected cache entry shape, for example:
  - entry metadata: `key`, `ttlSeconds`, `fetchedAt`, `expiresAt`, `isRefreshing`, `lastError`
  - payload data: the existing Market Overview payload returned by `MarketCache._payload(...)`
- Representative payloads already proven to round-trip through JSON without semantic drift:
  - fresh/live Market Overview payload
  - stale + refreshing payload
  - fallback payload
- The round-trip must preserve payload metadata fields already covered by T-641 tests, including:
  - `freshness`, `isFallback`, `isStale`, `isPartial`, `isSynthetic`, `isRefreshing`
  - `lastError`, `source`, `sourceLabel`, `asOf`, `updatedAt`
  - `providerHealth`, `evidenceSnapshot`, `sourceConfidence`, `scoreReliabilityAllowed`

## Runtime internals that must not be serialized

- `threading.RLock`
- `Future`
- executor state
- fetcher/fallback callables
- process-local leases, refresh generation counters, or similar coordination state unless a later design explicitly defines them

## Safest future implementation boundary

- Any future Redis/Valkey work must stay behind the existing `MarketCache` API as a disabled-by-default adapter.
- Default behavior must not change; the local in-memory backend and default null remote backend remain authoritative.
- A first remote backend may store only JSON-safe payload projections.
- Remote reads, hydration, cache-warming authority, and fallback/live authority are out of scope for the first real adapter.
- Distributed locking, distributed SWR, leases, and cross-process cold-start coalescing are separate design problems and must be specified before enablement.
- A real network adapter must define explicit timeout, failure, and backpressure policy before enablement.
- Request success must not depend on remote write success.
- Remote persist must not become a provider route failure source.

## Explicitly forbidden in a first Redis implementation

- provider routing or provider order changes
- provider budget changes
- live-call behavior changes
- TTL, SWR, cold-start, fallback retention, or background refresh semantic changes
- fallback/live authority or freshness-label changes
- API or schema changes
- scoring or decision changes
- scanner, portfolio, Options, backtest, DuckDB/quant, auth/RBAC, frontend, or admin-log changes
- cache key semantic changes

## Operational rule

- If future Redis/Valkey work needs new env/config flags, dependencies, runtime enablement, timeout policy, or failure-handling semantics outside this boundary, stop and open a separate scoped task instead of broadening the mirror-policy pass.
