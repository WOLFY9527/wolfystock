# Public API Abuse Limiter Operator Note

## Scope

The public API abuse limiter is a process-local guard for bursts of unauthenticated public API error responses. It applies only to `/api/v1/` requests that are not exempt, are not `OPTIONS`, and do not carry a valid session cookie.

Tracked responses are limited to public error bursts with status codes `400`, `401`, `403`, `405`, and `422`. The limiter is not a replacement for authenticated login rate limits, upstream WAF rules, ingress throttling, or application authorization checks.

## Configuration

The limiter reads these environment variables at request time:

| Variable | Default | Bounds | Meaning |
| --- | ---: | ---: | --- |
| `PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS` | `300` | `60` to `3600` | Rolling window for public error bursts. |
| `PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES` | `12` | `1` to `100` | Maximum tracked failures before returning `429`. |
| `PUBLIC_API_ABUSE_LIMIT_MAX_BUCKETS` | `4096` | `16` to `65536` | Maximum process-local client buckets retained before oldest-bucket eviction. |

Invalid integer values fall back to the documented defaults. Out-of-range values are clamped to the documented bounds. The `Retry-After` response header uses the bounded window value.

## Sanitized Observability

Use `api.middlewares.public_abuse_limiter.get_public_api_abuse_limiter_snapshot()` for process-local diagnostics. The snapshot exposes aggregate counters only:

- bucket count
- total tracked failures
- maximum failures in any bucket
- number of buckets currently at or above the limit
- oldest bucket age in seconds
- bounded window and failure-limit settings
- bounded max-bucket setting
- `processLocal=true`
- `identityRedaction=client_identity_not_exposed`

The snapshot must not expose bucket keys, request bodies, raw client IPs, cookies, session IDs, authorization headers, arbitrary request headers, validation internals, stack traces, or raw exception text.

## Privacy Expectations

Limiter responses are intentionally generic:

```json
{"error":"rate_limited","message":"Too many public API errors; retry later."}
```

Operators should correlate limiter behavior with ingress or platform telemetry by time window and aggregate volume. Do not add raw request payloads or raw client identifiers to limiter logs or responses.

## Limitations

State is stored in process memory. Buckets are not shared across workers, hosts, restarts, deploys, or autoscaling events. Use upstream ingress controls for fleet-wide enforcement and long-term analytics.

When bucket count exceeds `PUBLIC_API_ABUSE_LIMIT_MAX_BUCKETS`, expired buckets are pruned first, then the oldest remaining buckets are evicted until the cap is respected. This keeps memory growth bounded without changing the normal request path for valid authenticated traffic.
