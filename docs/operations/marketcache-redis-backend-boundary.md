# MarketCache Redis Backend Boundary

Status: design boundary only. Redis/Valkey is not implemented or enabled.

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
- Default behavior must not change; the local in-memory backend remains the default.
- A first remote backend may store only JSON-safe payload projections.
- Distributed locking, distributed SWR, cross-process cold-start coalescing, lease ownership, and generation semantics are separate design problems and must be specified before enablement.

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

- If future Redis/Valkey work needs config/env/dependencies/runtime changes outside this boundary, stop and open a separate scoped task instead of broadening the first backend pass.
