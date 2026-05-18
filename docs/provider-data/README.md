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

## Related Domains

- [Scanner](../scanner/README.md)
- [Market Overview](../market-overview/README.md)
- [Liquidity](../liquidity/README.md)
- [Rotation](../rotation/README.md)
- [Options](../options/README.md)
- [Backtest](../backtest/README.md)
