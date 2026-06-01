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
  windows. Runtime activation probes a small high-value set first (market
  benchmarks, ETF proxies, and representative constituents) before attempting
  the larger theme universe under internal per-window, per-batch, and total
  provider budgets. If credentials, feed entitlement, symbol data, or provider
  budget are unavailable, the provider falls back to degraded yfinance
  daily/proxy evidence only and must not synthesize intraday windows or mark
  fallback/static data live.
- Operator-approved environments may raise only the bounded Alpaca runtime
  waits with
  `ROTATION_RADAR_ALPACA_PER_WINDOW_TIMEOUT_SECONDS`,
  `ROTATION_RADAR_ALPACA_TOTAL_PROVIDER_BUDGET_SECONDS`, and
  `ROTATION_RADAR_ALPACA_PROVIDER_DEADLINE_SECONDS`. Absent, blank, malformed,
  zero, or negative values preserve defaults (2.5s per window, 8.0s total
  provider budget, 3.0s outer quote-provider deadline), and positive values are
  capped locally. These knobs are not provider activation, routing/order,
  fallback, scoring/ranking/category, source-authority, or entitlement
  controls.
- Provider activation diagnostics live under
  `metadata.quoteProvider.providerDiagnostics` / quote-provider metadata. They
  expose credential presence, safely inferable credential source, missing env
  credential field names, configured feed, construction status, per-window
  `requestWindowResults` for 5m/15m/60m/1d, sanitized failure classes
  (`missing_credentials`, `entitlement_denied`, `auth_failed`,
  `interval_mapping`, `market_session`, `calendar`, `rate_limited`, `timeout`,
  `empty_response`, `symbol_not_found`, `provider_error`, `unknown`), capped
  `symbolFailureSamples`, configured-provider fulfilled/missing window aliases,
  staged activation limits (`maxSymbolsPerWindow`, `maxProbeSymbols`,
  `perWindowTimeout`, `totalProviderBudget`, `providerDeadlineSeconds`),
  staged activation fields (`probeSymbolCount`, `fullUniverseSymbolCount`,
  `providerBudgetExceeded`, `timeoutSymbolCount`,
  `skippedDueToBudgetCount`, `activationScope`,
  `minimumActivationCoverageMet`), yfinance fallback usage kept separate from
  Alpaca fulfillment,
  `liveActivationStatus`, `activationBlocker`, recommended activation
  action/hint, and final trust/source-tier classification without exposing raw
  credential values.
- `consumerEvidenceSnapshot` is the consumer-facing projection for Rotation
  Radar evidence. It is additive and whitelist-only: market/as-of/freshness,
  fallback/stale/partial flags, headline/observation/taxonomy counts, sanitized
  reason codes, provider state summary, ETF proxy-only leadership summary, and
  per-theme public quality flags. It deliberately excludes credentials/env
  visibility, missing env names, provider budgets/deadlines, request-window
  results, raw failure samples, source-authority router internals, activation
  hints/recommended actions, proxy environment, admin diagnostics, raw evidence
  signals, score/weight breakdowns, ranking trust, ETF authority evidence rows,
  and raw provider payloads/errors. It must not recompute source authority,
  score authority, ranking, headline eligibility, provider routing, or cache
  behavior.
- Rotation Radar now also exposes additive `themeFlowSignal` on each US theme
  row plus `summary.rotationFamilyRollup` /
  `consumerEvidenceSnapshot.rotationFamilyRollup` for investor-readable AI,
  SaaS/software, semiconductors, energy, and defensive family rollups. These
  signals are built only from existing theme outputs and the shared
  `investor_signal_model` contract: `themeFlowState`, capped confidence,
  leadership/breadth/relative-strength evidence, sanitized reason codes, and
  explanatory text are observation-only disclosures. They must not change or be
  used to infer `rankEligible`, `headlineEligible`, `rankingLane`,
  `sourceAuthorityAllowed`, `scoreContributionAllowed`, provider routing, cache
  authority, or category promotion semantics. Fallback/static/taxonomy-only and
  partial evidence remains non-headline and non-score-grade.
- Rotation UI changes must not alter score, ranking, provider, or evidence
  semantics unless explicitly scoped.
