# WolfyStock Rotation Docs

Status: current rotation domain entry point.

Use this lane before changing rotation radar UI, ranked theme/sector evidence,
fund-flow interpretation, or rotation evidence disclosure.

## Current Authority

- [Provider And Data Docs](../provider-data/README.md)
- [Frontend Visual System](../frontend/visual-system.md)
- [Frontend Validation Playbook](../frontend/validation-playbook.md)
- [Data Quality User Disclosure Policy](../audits/data-quality-user-disclosure-policy.md)

## Current Rules

- Rotation Radar should lead with ranked themes/sectors and selected-theme
  evidence, not implementation diagnostics.
- Freshness, source confidence, and fallback limitations should remain visible
  near the rotation conclusion.
- Fallback/static, synthetic, unavailable, and taxonomy-only Rotation Radar
  themes remain visible for observation, but are not eligible for headline or
  strongest-theme ranking.
- Rotation Radar API clients must consume `summary.strongestThemes` and
  `summary.acceleratingThemes` as headline lanes only when summary items expose
  `rankEligible: true`, `headlineEligible: true`, and
  `rankingLane: "headline"`. Fallback/static/taxonomy-only themes stay in
  observation or taxonomy lanes (`summary.observationThemes`,
  `summary.taxonomyThemes`, and the full `themes` list) with
  `summary.noHeadlineReason` populated when no real-data theme is headline
  eligible.
- Theme Registry v2 metadata should keep constituent definitions, inclusion
  notes, ETF proxy coverage, and index/asset proxy concepts explicit. ETF
  proxies are relative-strength and participation proxies only, not real
  fund-flow dollar claims.
- US Rotation Radar quote evidence uses the configured Alpaca market-data
  credentials (`ALPACA_API_KEY_ID`, `ALPACA_API_SECRET_KEY`, and
  `ALPACA_DATA_FEED`) when present to populate bounded 5m/15m/60m/1d OHLCV
  windows. If credentials, feed entitlement, or symbol data are unavailable,
  the provider falls back to degraded yfinance daily/proxy evidence only and
  must not synthesize intraday windows or mark fallback/static data live.
- Provider activation diagnostics live under
  `metadata.quoteProvider.providerDiagnostics` / quote-provider metadata. They
  expose credential presence, safely inferable credential source, missing env
  credential field names, configured feed, construction status, per-window
  `requestWindowResults` for 5m/15m/60m/1d, sanitized failure classes
  (`missing_credentials`, `entitlement_denied`, `auth_failed`, `rate_limited`,
  `timeout`, `empty_response`, `symbol_not_found`, `provider_error`,
  `unknown`), capped `symbolFailureSamples`, fallback usage, recommended
  activation action/hint, and final trust/source-tier classification without
  exposing raw credential values.
- Rotation UI changes must not alter score, ranking, provider, or evidence
  semantics unless explicitly scoped.
