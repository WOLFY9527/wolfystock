# Market Intelligence Smoke Checklist

Status: backend-only smoke/checklist coverage for the current Market Intelligence cluster.

Scope:
- Market Overview panel/freshness backend contracts
- Core quote indicators for SPX, VIX, HSI, US10Y, DXY, BTC, and existing CN/HK indices
- Official macro registry/transport coverage and delayed/unavailable semantics
- Liquidity Monitor evidence/backfill disclosure
- Rotation Radar evidence/projection disclosure
- Sector Rotation projection disclosure
- Market Temperature / Market Briefing degraded-state semantics

Run:

```bash
python3 -m pytest tests/test_market_intelligence_smoke_checklist.py -q
python3 -m pytest \
  tests/test_market_overview_core_quote_repair.py \
  tests/test_market_overview_snapshot.py \
  tests/test_liquidity_monitor_service.py \
  tests/test_rotation_theme_registry.py \
  tests/test_market_rotation_radar_service.py \
  tests/test_market_temperature_input_snapshot.py \
  tests/test_market_cache_fallback_contracts.py \
  tests/api/test_market_endpoint_provider_regressions.py \
  tests/api/test_market_macro_cards.py \
  tests/api/test_liquidity_monitor.py \
  tests/api/test_market_rotation_radar.py \
  tests/api/test_market_temperature.py \
  tests/api/test_market_briefing.py -q
python3 -m py_compile tests/test_market_intelligence_smoke_checklist.py
git diff --check
./scripts/release_secret_scan.sh
```

Manual backend endpoints to probe:
- `GET /api/v1/market-overview/indices`
- `GET /api/v1/market-overview/volatility`
- `GET /api/v1/market-overview/macro`
- `GET /api/v1/market-overview/sentiment`
- `GET /api/v1/market/temperature`
- `GET /api/v1/market/market-briefing`
- `GET /api/v1/market/liquidity-monitor`
- `GET /api/v1/market/rotation-radar?market=US`
- `GET /api/v1/market/sector-rotation`

Expected degraded-state semantics:
- Fallback, stale, delayed, partial, or unavailable payloads must not appear live/fresh.
- Core quote indicators must keep `source`, `sourceLabel`, `sourceTier`, `asOf`, `freshness`, and `trustLevel` when available, and any delayed/fallback/unavailable row must carry an explicit `degradationReason`.
- Core source activation diagnostics for SPX, VIX, US10Y, DXY, and CN00Y must expose
  `providerAttempted`, `providerClass`, `officialOverlayAttempted`,
  `officialOverlayAvailable`, `officialOverlayFailureReason`, and
  `activationHint`; unavailable or stale official overlays must keep any
  visible yfinance/proxy/static fallback row capped and non-live.
- N/A is allowed only with explicit unavailable evidence; do not mask it as live or fresh.
- Official macro rows for Treasury/FRED daily and monthly releases must keep
  `official_public` provenance, provider `asOf`, and delayed/stale/unavailable
  disclosure; effective fed funds, CPI YoY, PPI YoY, and credit-spread proxy
  rows must not appear realtime.
- Snapshot reuse may keep prior real values visible, but the payload and item freshness must disclose `stale` or `fallback`.
- Liquidity Monitor evidence must keep degraded inputs explicit through
  indicator evidence and `coverageDiagnostics` instead of silently counting
  them as healthy.
- Liquidity Monitor `coverageDiagnostics` must keep unavailable or partial
  inputs capped/excluded from strong score contribution and must not label
  fallback/static data as live or fresh.
- Rotation Radar and Sector Rotation must keep proxy/taxonomy/fallback evidence visible through metadata, evidence snapshots, and source freshness fields.
- Fallback/static Rotation Radar themes must stay observation-only and out of headline rankings.
- Observation-only Rotation Radar themes must not appear in `summary.strongestThemes` or `summary.acceleratingThemes`.
- `summary.observationThemes` and `summary.taxonomyThemes` must remain separate from headline lists.
- Rotation Radar Theme Registry v2 metadata must separate ETF proxies from index/asset concepts and keep proxy evidence framed as ETF proxy / participation proxy / relative strength proxy only.
- Headline indicators must not render ambiguous N/A when a backend item has a numeric value.
- Missing headline indicator values must include `isUnavailable`, `degradationReason`, non-live `freshness`, and weak/unavailable trust metadata.
- Liquidity Monitor provider activation diagnostics must include
  `requiredProviderClass`, `configuredProviderAvailable`,
  `realSourceAvailable`, `proxyOnly`, `observationOnly`,
  `scoreContributionAllowed`, `missingProviderReason`, and
  `paidDataLikelyRequired` so weak or proxy-only inputs cannot silently count
  as strong liquidity evidence.
- Liquidity Monitor score contribution stays blocked for the CN/HK connect
  flow, CN money-market fallback, and futures/premarket classes until a real
  audited provider is available; yfinance proxies remain capped rather than
  live.
- Market Temperature and Market Briefing must degrade to insufficient-data posture when reliable inputs are missing; they must not emit strong bullish/bearish action language from fallback-only inputs.
- Market Temperature and Market Briefing trust fields (`trustLevel`, `sourceTier`, `scoreCap`, `conclusionAllowed`, `degradationReasons`) must cap stale, fallback, unavailable, synthetic, mixed, or low-coverage evidence before strong conclusions are allowed.
- Market Temperature disabled states must expose explicit `temperatureAvailable=false`, `disabledReason=insufficient_reliable_inputs`, `unavailableReason`, `insufficientReliableInputs`, and `requiredReliableInputCount` metadata instead of collapsing to ambiguous `N/A`.

Backend-only:
- This checklist is backend-only.
- It is not frontend visual validation.
- It is not browser/layout acceptance.
- It does not validate copy hierarchy, charts, spacing, or route visuals.

Advisory-only:
- These endpoints are observation and disclosure surfaces, not trading or investment signal execution.
- Do not treat Rotation Radar ranking, Sector Rotation ordering, Liquidity score, Temperature score, or Briefing text as order intent.
- Do not use this checklist as evidence for scanner execution, backtest execution, portfolio mutation, broker/order flows, or auth/RBAC behavior.

Out of scope:
- No provider order changes.
- No new providers.
- No MarketCache core changes.
- No provider score/stage formula changes.
- No API schema breaking changes.
- No frontend changes.
- No DB changes.
- No auth/RBAC changes.
- No LLM, Portfolio, Backtest, Options, or accounting changes.
