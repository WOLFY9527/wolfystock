# WolfyStock Provider And Data Docs

Status: current provider/data domain entry point.

Use this lane before changing provider order, fallback, freshness labels,
source confidence, cache/SWR behavior, provider budgets, quota/circuit policy,
data-quality disclosure, scanner eligibility, or options/backtest data
boundaries.

## Current Authority

- [Provider Data Freshness Reliability Guide](../audits/provider-data-freshness-reliability-guide.md)
- [Provider Data Incident Runbook](../audits/provider-data-incident-runbook.md)
- [Market Data Provider Upgrade Matrix](../audits/market-data-provider-upgrade-decision-matrix.md)
- [Provider Capability Metadata](../operations/provider-capability-metadata.md)
- [Provider Budget And Routing Rules](../codex/WOLFYSTOCK_PROVIDER_BUDGET_AND_ROUTING_RULES.md)
- [Data Quality User Disclosure Policy](../audits/data-quality-user-disclosure-policy.md)
- [Provider/Data/Options Index](../audits/index-provider-data-options.md)

## Current Rules

- Keep provider ordering, fallback, retry/circuit state, source disclosure,
  local/cache-first behavior, and freshness labels explicit.
- Do not deepen fallback, reorder providers, or hide stale/partial data without
  explicit task scope and validation.
- Single provider failure should not collapse the whole analysis flow unless a
  task explicitly requires fail-fast behavior.
- User-facing pages must disclose fallback, stale, partial, or unavailable data
  honestly without making degraded data look fully live.

## Disabled Cache-Only Diagnostics

- `authorized.cn_hk_connect_flow` is disabled by default. When
  `CN_HK_CONNECT_FLOW_PROVIDER_ENABLED=true` and
  `CN_HK_CONNECT_FLOW_CACHE_PATH` points to a local JSON cache, Market Overview
  may surface CN/HK connect-flow diagnostics from that cache only.
- The adapter does not make live provider calls. `CN_HK_CONNECT_FLOW_API_KEY` is
  optional metadata for operator environments and is never returned by Provider
  Operations.
- CN/HK connect-flow diagnostics remain `observationOnly=true` and
  `scoreContributionAllowed=false`; Liquidity Monitor must not score them.
- If the cache is missing, malformed, stale, permission-denied, or below the
  required northbound/southbound coverage, `/api/v1/market/cn-flows` falls back
  to the existing static fallback response.

## Related Domains

- [Scanner](../scanner/README.md)
- [Market Overview](../market-overview/README.md)
- [Liquidity](../liquidity/README.md)
- [Rotation](../rotation/README.md)
- [Options](../options/README.md)
- [Backtest](../backtest/README.md)
