# Market Source Activation Blueprint

Status: implementation-ready blueprint for T-1764.

This is a docs-only activation plan. It does not change market data adapters,
credentials, cache behavior, database state, scanner state, broker sync,
pricing, storage, auth, or any source-family runtime path.

## Executive Decision: First 3 Source Families To Activate

Activate source families in this order:

1. Official VIX / volatility.
   - First because it is a narrow official-public series family with high impact
     on Market Overview volatility, Liquidity Monitor VIX pressure, Market
     Temperature, Home briefing, and Decision Cockpit.
   - Initial proof must use the existing official macro cache/readiness path for
     `VIXCLS`; yfinance or other public proxy rows remain delayed/capped and
     non-score-grade.
2. Macro / rates / Fed liquidity.
   - Second because it reuses the official macro transport/cache model and
     unlocks the broadest downstream evidence set: rates, USD pressure, credit
     stress, Fed liquidity, Market Temperature, Home briefing, and Decision
     Cockpit.
   - Treat Treasury/FRED daily rows separately from Fed weekly liquidity rows;
     partial coverage does not become score-grade.
3. US index / ETF quote coverage, then sector/rotation quote coverage on the
   same credential/feed boundary.
   - Third because Rotation Radar and sector leadership need configured quote
     coverage across market benchmarks and ETF proxies before headline lanes can
     carry real evidence.
   - The smallest safe task starts with the existing stable probe symbols
     `SPY`, `QQQ`, `IWM`, `SMH`, `SOXX`, and `IGV`, then expands only after
     feed entitlement, freshness, coverage, and source-authority gates pass.

Do not activate real funds-flow, options gamma/dealer exposure, CN/HK connect
flow, or CN money-market score contribution before the above three families are
proven and reviewed. Those families have stronger entitlement, methodology, or
manual-review requirements.

## Current Consumer Surfaces Affected

| Surface | Current endpoint / route | Dependency summary | Activation impact |
| --- | --- | --- | --- |
| Market Overview | `/api/v1/market-overview/{indices,volatility,sentiment,funds-flow,macro}` | `MarketOverviewService` panel cache, official macro overlay, quote-derived panels. | Official volatility, macro/rates, and quote coverage increase real evidence count without changing consumer copy semantics. |
| Liquidity Monitor | `/api/v1/market/liquidity-monitor` | Cache-only reads of crypto, volatility, rates, macro, FX/commodities, funds-flow, breadth, CN/HK, futures. | Official volatility and macro/rates/Fed rows can convert selected families from observation-only to score-grade only when `scoreContributionAllowed=true`. |
| Rotation Radar | `/api/v1/market/rotation-radar?market=US` | Configured Alpaca quote provider plus yfinance fallback; non-US remains taxonomy-only. | US index/ETF and sector quote coverage is required before headline/accelerating lanes can be populated by real evidence. |
| Home briefing | `/api/v1/market/market-briefing` | Market Overview trust snapshot plus downstream liquidity/rotation context. | Home is downstream; validate after Market Overview, Liquidity, and Rotation evidence gates improve. |
| Decision Cockpit | `/api/v1/market/decision-cockpit` | Composes Market Overview regime, research preview, and options observation. | Cockpit should remain downstream; do not tune confidence gates before upstream source authority is proven. |

## Existing Provider / Cache Path

Key static findings:

- Market Overview panel entry points are `get_indices`, `get_volatility`,
  `get_funds_flow`, and `get_macro` in
  `src/services/market_overview_service.py:1136`, `:1141`, `:1155`, and
  `:1160`.
- Market Overview writes successful provider-backed snapshots through
  `_cached_payload`; fallback-only or no-usable-data responses are rejected
  before cache storage, then `MarketCache.get_or_refresh` may serve stale or
  fallback snapshots with explicit metadata
  (`src/services/market_overview_service.py:3522` and `:3550`).
- Official macro transport declares FRED/Treasury source families including
  `VIXCLS`, Treasury rate series, credit stress, USD pressure, and Fed
  liquidity series
  (`src/services/official_macro_transport.py:23`, `:47`, `:48`, and `:56`).
- Official daily and weekly freshness policies are encoded in Market Overview
  (`src/services/market_overview_service.py:125`, `:141`, and `:207`) and
  official macro transport
  (`src/services/official_macro_transport.py:107` and `:108`).
- Liquidity Monitor defaults to cache-only reads with
  `allow_external_provider_calls=False`, then reads existing panels for
  volatility, rates, macro, funds-flow, breadth, CN/HK, and futures
  (`src/services/liquidity_monitor_service.py:311` and `:326`).
- Liquidity provider activation policy is explicit per indicator family:
  VIX, USD, rates, Fed liquidity, ETF flow, US breadth, CN/HK, CN money-market,
  and futures (`src/services/liquidity_monitor_service.py:205`).
- Rotation Radar uses a configured-provider-first quote path with yfinance
  fallback; its provider order is Alpaca then yfinance
  (`src/services/rotation_radar_quote_provider.py:1`, `:33`, and `:39`).
- Rotation Radar uses a bounded stable activation probe of `SPY`, `QQQ`, `IWM`,
  `SMH`, `SOXX`, and `IGV`
  (`src/services/rotation_radar_quote_provider.py:40`).
- Market data readiness diagnostics are explicitly local-only, checking env
  shape, filesystem presence, and importability without provider calls, network
  connections, or parquet reads
  (`src/services/market_data_readiness_diagnostics.py:1` and `:135`).

## Source-Family Inventory

| Source family | Existing path | Credential/feed entitlement requirement | Freshness SLA | Source-authority rule | Score-grade eligibility rule | Smallest safe implementation task |
| --- | --- | --- | --- | --- | --- | --- |
| US index / ETF quotes | `data_provider/base.py` routes US index quotes through yfinance only today (`:1683`); US stock quotes attempt Alpaca first when complete credentials exist, then yfinance (`:1757`, `:1773`, `:1829`). Rotation quote provider uses Alpaca then yfinance (`src/services/rotation_radar_quote_provider.py:39`). | Alpaca requires key id, secret key, and configured data feed (`data_provider/provider_credentials.py:164`); yfinance is public proxy and not sufficient for score-grade authority. | Rotation uses 5m/15m/60m/1d windows with bounded waits; shared radar snapshot TTL is 180 seconds (`src/services/market_rotation_radar_service.py:52` and `:82`). | Alpaca coverage may be considered only after feed, freshness, and source metadata pass. yfinance is delayed/proxy only. | Score-grade only if configured-provider quotes are fresh enough, coverage is complete enough, not fallback/stale, and explicit authority fields are true. | Add an offline activation checklist and focused tests around Alpaca credential/feed diagnostics for the stable ETF probe; do not change provider order. |
| Official VIX / volatility | Market Overview volatility panel plus official macro overlay; `VIXCLS` has official daily freshness policy (`src/services/market_overview_service.py:141`). | FRED official-public access must be configured when live fetch is used; cache/readiness tasks must not print credential values. | Daily US weekday T+1 policy: max 4 calendar days and 2 business days in existing contract. | Official `VIXCLS` row must be present, fresh by policy, and have valid official source metadata. Proxy volatility rows stay capped. | VIX contributes only when official row passes freshness and source authority; proxy-only VIX remains observation-only in Liquidity (`docs/liquidity/README.md:81`). | Start with cache-readiness proof for `VIXCLS`, then run mocked official macro/market overview tests; no live probe in the implementation task unless explicitly scoped. |
| Macro / rates / Fed liquidity | Official macro transport supports Treasury rates, FRED rates, USD pressure, credit stress, and Fed liquidity (`src/services/official_macro_transport.py:29`, `:47`, `:48`). Market Overview promotes Fed liquidity rows only when the official cache bundle is complete (`src/services/market_overview_service.py:8819`). | FRED/Treasury official-public access; Fed liquidity does not become active from a partial cache. | Daily rate rows use T+1 style freshness; Fed liquidity rows use weekly H.4.1 T+7 style freshness. | Each series must pass source metadata, freshness, and required series coverage; successful provider capability alone is not enough. | Score-grade only when each required bundle reports `scoreContributionAllowed=true`; missing series fail closed. | Activate official rates and Fed liquidity as separate serial tasks after VIX; each task adds offline cache/readiness tests before any prewarm/runbook step. |
| US breadth / internals | Inert contract defines advancers, decliners, unchanged, A/D ratio, new highs/lows, and high/low ratio (`src/services/us_breadth_contracts.py:21`). Polygon adapter computes from grouped daily rows but requires credentials and coverage (`src/services/polygon_us_breadth_provider.py:1`). | Authorized or official breadth feed required; Polygon path reads `POLYGON_API_KEY` and must prove licensing/coverage before use. | Same-session delayed or daily close, with Polygon coverage threshold and lag checks (`src/services/polygon_us_breadth_provider.py:46`). | Representative samples and sector ETF proxies are not broad-market breadth authority. | Score-grade only when authorized feed, freshness, and min-coverage gates pass; otherwise remains missing or observation-only. | Build a provider-free readiness table and mocked Polygon activation test bundle before any live or cache task. |
| Sector / rotation quote coverage | Rotation Radar quote provider uses configured Alpaca OHLCV windows and yfinance fallback (`docs/rotation/README.md:36`). | Alpaca credentials plus feed entitlement; feed, symbol coverage, and provider budget must be reviewed. | 5m/15m/60m/1d windows, default bounded waits, and shared snapshot TTL. | Fallback/static/taxonomy-only/synthetic/unavailable evidence is excluded from headline lanes (`docs/rotation/README.md:21`). | Headline eligibility requires real-data quote coverage, source authority, and trust gates; ETF proxy-only leadership still cannot broaden headlines by itself. | First run the stable ETF probe in a controlled implementation task; only then expand to the larger theme universe. |
| Funds-flow proxy vs real flow | Current funds-flow is quote-derived proxy evidence, including QQQ/IWM-derived context (`docs/liquidity/README.md:49`). | Real flow needs `authorized.us_etf_flow`; likely paid/reviewed data. | Do not define SLA until feed contract is reviewed. Proxy rows inherit quote freshness but not real-flow authority. | ETF price/relative-strength proxy is not real flow. | Proxy-only rows cannot become score-grade without an explicit reviewed allowlist and tests; default stays observation-only. | Split copy/diagnostics from real-flow activation. Real-flow provider selection is a manual-review task after the first three source families. |
| Options gamma / dealer exposure future dependency | Options observation contract exists and is intentionally observation-only; GEX/gamma fields are future-gated (`docs/options/options-market-structure-prerequisite-manifest.md:1`). | Must prove provider identity, plan tier, entitlement, redistribution rights, decision-use rights, provenance, freshness, coverage, and manual review (`docs/options/options-market-structure-prerequisite-manifest.md:46`). | Undefined until provider and methodology gates are approved. | Methodology and provider authority are separate; missing proof keeps the family blocked. | Current contract is `observationOnly=true` and `decisionGrade=false`; no score-grade adoption is approved. | Keep deferred. The next safe task is a proof-bundle template and offline methodology tests only. |
| CN market data family | CN/HK index context, CN/HK flow cache, CN money-market cache, pytdx/AKShare health diagnostics are discoverable. Provider docs state CN/HK connect flow is disabled by default and cache-only when enabled (`docs/provider-data/README.md:34`); CN money-market is cache-only (`docs/provider-data/README.md:46`). | CN/HK flow needs explicit cache path and reviewed feed rights; CN money-market cache path has no key requirement; pytdx/AKShare remain conservative diagnostics. | CN money-market max delay is 7 days (`src/services/cn_money_market_rates_contracts.py:34`). CN/HK index/flow SLA remains source-specific. | CN provider health stays metadata-only; pytdx and AKShare must remain cautious public/proxy diagnostics. | CN/HK flow, CN money-market fallback, and futures/premarket score contribution remain disabled until audited real source exists (`docs/liquidity/README.md:66`). | Do not include in first activation wave. Create a separate CN source review after US official/quote families are stable. |

## Source-Authority Rule

Source authority must be explicit and surface-specific. A provider name, source
label, cache hit, high coverage value, or successful response is not enough.
If entitlement, freshness, coverage, source metadata, and right-to-display are
not all established for the source family and surface, the output must fail
closed to unavailable, delayed, partial, or observation-only.

## Score-Grade Eligibility Rule

A source-family input is score-grade only when all of these are true:

- observed payload is real for the named family, not fallback, synthetic,
  stale, proxy-only, or taxonomy-only;
- freshness policy passes for that family;
- coverage threshold passes for all required inputs;
- source authority is explicitly granted for the surface;
- `scoreContributionAllowed=true` is produced by the existing gate;
- consumer projection keeps admin-only metadata out of default surfaces.

Do not loosen confidence or conclusion gates before this rule passes. Proxy-only
data can remain visible as observation context, but must not be counted as
score-grade evidence.

## Protected-Domain Boundary

This blueprint does not authorize:

- provider order changes;
- new live provider paths;
- credential/feed entitlement changes;
- cache TTL, SWR, cold-start, or fallback behavior changes;
- cache refreshes, prewarm runs, or cache mutation;
- DB writes, migrations, scanner runs, broker sync, pricing, storage, auth,
  session, RBAC, accounting, backtest, or LLM changes;
- consumer copy that implies stronger evidence than the source authority proves.

Any implementation task that touches one of those domains must be serial and
manual-review.

## Validation Commands

For this docs-only blueprint:

```bash
git diff --check origin/main...HEAD
git diff --check
bash scripts/release_secret_scan.sh --base-ref origin/main
```

If no docs lint command is present, use grep-based review against the changed
Markdown files with the prohibited vocabulary from
`docs/codex/NO_ADVICE_REGRESSION_GUARDS.md`; do not copy that vocabulary into
this artifact.

For future implementation tasks, use mocked/offline validation first:

```bash
python -m pytest tests/test_market_intelligence_smoke_checklist.py -q
python -m pytest tests/test_market_overview_api.py -k "official_macro or fed_liquidity" -q
python -m pytest tests/test_liquidity_monitor_service.py tests/api/test_liquidity_monitor.py -q
python -m pytest tests/test_market_rotation_radar_service.py tests/api/test_market_rotation_radar.py -q
python -m pytest tests/test_market_data_readiness_diagnostics.py tests/api/test_market_data_readiness.py -q
python -m pytest tests/test_polygon_us_breadth_provider.py tests/test_us_breadth_contracts.py -q
python -m pytest tests/test_options_market_structure_observation.py tests/test_options_chain_gamma_observation_adapter.py tests/test_options_gamma_methodology_contract.py -q
```

Live provider probes, cache prewarm, or feed entitlement checks are not part of
this blueprint validation and must be separately authorized.

## Rollback Strategy

Current docs-only rollback:

```bash
git revert <T-1764-commit>
```

Future implementation rollback pattern:

- disable only the activated source family;
- preserve existing fallback/stale/unavailable labels;
- remove or pause any new cache prewarm schedule;
- leave consumer surfaces in observation-only or unavailable posture;
- do not adjust score/confidence gates to hide a failed source-family rollback;
- rerun the same offline tests plus source-family-specific diagnostics.

## Parallelization / Serialization Map

Parallelizable:

- docs, contracts, and mocked tests for VIX, official macro, readiness
  diagnostics, US breadth contracts, and options methodology;
- frontend copy/diagnostic wording that does not change source authority,
  scoring, provider routing, cache behavior, or API shape;
- read-only inventory of credentials/feed requirements without reading secret
  values.

Must be serial:

- official VIX activation before broader official macro/rates/Fed liquidity;
- official macro cache/prewarm semantics after cache-readiness tests;
- Alpaca US index/ETF quote activation before Rotation Radar headline-lane
  expansion;
- US breadth/internals provider activation after source and coverage review;
- real funds-flow provider selection and entitlement review;
- options gamma/dealer exposure provider and methodology proof;
- CN/HK flow and CN money-market source authority review.

Manual-review gates:

- any new provider or live-call path;
- credential/feed entitlement proof;
- right-to-display or redistribution proof;
- score-grade promotion;
- provider/cache/runtime behavior;
- Decision Cockpit confidence gate changes.

## Activation Task Queue

1. `T-1764-A`: Official VIX cache-readiness and mocked proof.
   - Scope: `VIXCLS`, Market Overview volatility, Liquidity VIX pressure.
   - Exit: official row passes freshness/source metadata tests; proxy VIX remains
     capped.
2. `T-1764-B`: Official macro/rates/Fed liquidity bundle readiness.
   - Scope: Treasury rates, SOFR/DFF/credit stress, USD pressure, Fed liquidity.
   - Exit: complete bundle coverage with source authority and explicit freshness.
3. `T-1764-C`: Alpaca US index/ETF quote activation gate.
   - Scope: stable ETF probe first, then sector/rotation quote coverage.
   - Exit: configured-provider coverage and freshness pass; yfinance fallback
     remains non-score-grade.
4. `T-1764-D`: US breadth/internals proof bundle.
   - Scope: advancers/decliners, unchanged, A/D ratio, highs/lows.
   - Exit: authorized feed and min-coverage proof; representative samples remain
     observation-only.
5. `T-1764-E`: Real funds-flow source review.
   - Scope: `authorized.us_etf_flow` or equivalent reviewed feed.
   - Exit: proxy-vs-real boundary locked before score-grade use.
6. `T-1764-F`: Options gamma/dealer exposure proof template.
   - Scope: provider rights, methodology, coverage/freshness, and observation
     contract only.
   - Exit: still observation-only unless a later protected-domain task explicitly
     changes that boundary.
7. `T-1764-G`: CN source-family review.
   - Scope: CN/HK index, connect flow, CN money-market rates, pytdx/AKShare
     diagnostics.
   - Exit: keep current diagnostics until audited source authority exists.
