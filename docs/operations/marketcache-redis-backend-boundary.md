# MarketCache Redis Backend Boundary

Status: disabled-by-default mirror client only. A Redis/Valkey adapter now exists as a persist-only client, but it is not wired into app startup or enabled by default.

## Current remote seam

- `MarketCache` currently exposes only a best-effort remote mirror seam behind `MarketCacheRemoteBackend`.
- The default backend remains `NullMarketCacheRemoteBackend`, so current behavior stays local-only unless a caller injects a test double.
- `MarketCacheRemoteMirrorDispatcher` exists as explicitly injected in-process mirror infrastructure. It wraps a supplied backend with a bounded single-worker queue, but it is not enabled by default.
- The seam is mirror-only: current runtime may project a JSON-safe document for persistence, but it does not read, hydrate, or re-authorize payloads from any remote store.
- `RedisMarketCacheRemoteBackend` exists behind this seam as a lazily imported persist-only client. Default MarketCache import/use does not require Redis/Valkey availability.
- `MARKET_CACHE_REMOTE_BACKEND=disabled` is the default. Redis mode requires explicit config and remains a mirror-only client intended to run behind `MarketCacheRemoteMirrorDispatcher`.

## Request-path persist policy

- Directly injected remote persist remains synchronous: `MarketCache.set(...)` calls the remote mirror after storing the local entry, and `_payload(...)` calls the same mirror path before returning the response payload.
- The dispatcher is the only current non-blocking mirror wrapper. It is process-local, drop-on-full, no-retry, and mirror-only; callers must inject it explicitly around an existing backend.
- A real network adapter must sit behind the dispatcher or another explicitly scoped non-blocking policy before enablement, otherwise it could add request-path latency to fresh hits, stale serves, cold fallback returns, and cold fetch success responses.
- Redis/Valkey deployment, runtime enablement, release evidence, and production validation remain separately scoped.
- Remote write success must remain best-effort only: request success must not depend on remote persist success, and remote persist must not become a provider route failure source.
- Remote persist must not change or gate fresh hit behavior, stale serve behavior, cold fallback behavior, cold fetch success behavior, background refresh behavior, payload freshness/fallback labels, provider calls, or local entry authority.
- `NullMarketCacheRemoteBackend` remains the default backend, and the local in-memory `MarketCache` remains authoritative.

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

- Redis/Valkey work stays behind the existing `MarketCache` API as a disabled-by-default adapter.
- Default behavior must not change; the local in-memory backend and default null remote backend remain authoritative.
- A first remote backend may store only JSON-safe payload projections.
- Remote reads, hydration, cache-warming authority, and fallback/live authority are out of scope for the first real adapter.
- Distributed locking, distributed SWR, leases, and cross-process cold-start coalescing are separate design problems and must be specified before enablement.
- A safe first networked mirror direction now exists as `MarketCacheRemoteMirrorDispatcher`: an in-process best-effort dispatcher with a bounded queue, drop-on-full behavior, no retries in the request path, and debug-only sanitized error reporting.
- The Redis/Valkey adapter uses an explicit short socket timeout from config, swallows persist failures with sanitized debug logging, and relies on the dispatcher for queue/backpressure behavior.
- Request success must not depend on remote write success.
- Remote persist must not become a provider route failure source.
- Remote reads remain out of scope, and the first safe implementation must not introduce distributed locks, distributed SWR, leases, cold-start coalescing, or multi-process generation semantics.

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
