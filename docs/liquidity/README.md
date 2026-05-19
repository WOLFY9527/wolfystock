# WolfyStock Liquidity Docs

Status: current liquidity domain entry point.

Use this lane before changing liquidity monitor UI, liquidity score display,
signal tables, source/risk rails, or liquidity-related freshness disclosure.

## Current Authority

- [Provider And Data Docs](../provider-data/README.md)
- [Frontend Visual System](../frontend/visual-system.md)
- [Frontend Validation Playbook](../frontend/validation-playbook.md)
- [Data Quality User Disclosure Policy](../audits/data-quality-user-disclosure-policy.md)

## Current Rules

- Liquidity pages should lead with liquidity score and signal table.
- Source/risk detail belongs in a bounded rail or disclosure.
- Do not let provider/cache/raw diagnostics become the default primary content.
- Do not imply execution readiness from liquidity evidence without an explicit
  safety-reviewed task.

## Backend Diagnostics

- Liquidity Monitor indicator payloads may include additive
  `coverageDiagnostics` metadata.
- Diagnostics must explain required, fulfilled, and missing inputs; source
  tier; freshness; trust level; score contribution; cap/degradation reason; and
  activation hints.
- Provider activation diagnostics must also expose `requiredProviderClass`,
  `configuredProviderAvailable`, `realSourceAvailable`, `proxyOnly`,
  `observationOnly`, `scoreContributionAllowed`, `scoreExclusionReason`,
  `requiredRealSourceForScore`, `proxyObservationOnlyReason`,
  `missingProviderReason`, and `paidDataLikelyRequired`.
- Missing, stale, fallback, synthetic, or unavailable inputs must not appear
  live or contribute strong score.
- `proxyOnly=true` with `realSourceAvailable=false` is observation-only by
  default and must not contribute to the liquidity score unless an explicit
  reviewed allowlist path is added with tests.
- CN/HK flow, money-market, futures, and proxy indicators must stay explicit
  about unavailable sources unless an existing configured and audited source
  provides real data.
- CN/HK flow, CN money-market fallback, and futures/premarket score
  contribution must remain disabled until `authorized.cn_hk_connect_flow`,
  `official_public.cn_money_market_rates`, or
  `exchange_or_broker_authorized.index_futures` is real and audited.
- US ETF flow and US breadth proxies must advertise
  `authorized.us_etf_flow` / `official_or_authorized.us_market_breadth`
  as missing real provider classes; yfinance proxy evidence may only stay
  delayed/capped rather than full-strength.
- VIX, DXY, and US Treasury yfinance proxy inputs may remain visible only as
  delayed/capped proxy diagnostics until official or authorized adapters are
  active. Binance spot crypto remains eligible as `exchange_public.crypto_spot`
  when fresh.
