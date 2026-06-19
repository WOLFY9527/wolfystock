# T-1764-C Quote Boundary Inventory

Status: implementation-ready inventory for T-1764-C.

This artifact is docs-only. It does not change provider runtime, provider
order, credential values, cache behavior, source-authority policy, headline
eligibility, Liquidity Monitor logic, Market Overview official macro logic, or
shared readiness diagnostics.

## Executive summary

- T-1764-C should start from the existing Rotation Radar configured-provider
  path, where provider order is fixed as `alpaca -> yfinance` and the bounded
  stable activation probe is `SPY`, `QQQ`, `IWM`, `SMH`, `SOXX`, `IGV`
  (`src/services/rotation_radar_quote_provider.py:39-46`).
- The same six ETFs are also the Rotation Radar ETF leadership authority spine:
  market benchmarks plus sector/software proxies needed to decide whether
  headline lanes can use real quote evidence
  (`src/services/market_rotation_radar_service.py:53-60`).
- Shared `data_provider/base.py` still routes US index realtime quotes through
  yfinance only, while US stock realtime quotes try Alpaca first when complete
  credentials are configured and then fall back to yfinance
  (`data_provider/base.py:1683-1740`, `data_provider/base.py:1742-1869`).
- yfinance remains a proxy/fallback boundary. It cannot grant source authority
  or score contribution for Rotation Radar headline use, and fallback/static/
  taxonomy-only evidence must stay out of headline ranking
  (`src/services/rotation_radar_quote_provider.py:1693-1749`,
  `src/services/market_rotation_radar_service.py:85-96`,
  `src/services/market_rotation_radar_service.py:4576-4581`).
- Alpaca credential/feed review for T-1764-C can stay offline and sanitized:
  key presence, secret presence, configured feed, credential source class,
  missing field names, request-window diagnostics, and activation blocker
  classes are already modeled without exposing secret values
  (`data_provider/provider_credentials.py:53-69`,
  `data_provider/provider_credentials.py:90-130`,
  `src/services/rotation_radar_quote_provider.py:181-194`,
  `src/services/rotation_radar_quote_provider.py:1028-1057`).
- T-1764-C must not edit official macro, Market Overview macro/rates/Fed
  liquidity, Liquidity Monitor, or shared readiness diagnostics files because
  those are part of T-1764-B's dependency boundary.

## Current quote path inventory

### Shared market-data route outside Rotation Radar

- US index realtime quotes are explicitly routed to yfinance only
  (`data_provider/base.py:1683-1740`).
- US stock realtime quotes use `alpaca -> yfinance` when Alpaca is configured,
  record `alpaca(incomplete)` when credentials are partial, and skip Alpaca
  when not configured (`data_provider/base.py:1742-1773`).
- If Alpaca is configured, the manager attempts Alpaca first and accepts the
  quote only when basic fields are present; otherwise it falls through to
  yfinance (`data_provider/base.py:1774-1829`, `data_provider/base.py:1829-1869`).
- This means T-1764-C should not assume a repo-wide US index/ETF path already
  uses Alpaca. The existing configured-provider-first contract is Rotation
  Radar specific.

### Rotation Radar quote path

- Rotation Radar provider order is fixed as `("alpaca", "yfinance")`
  (`src/services/rotation_radar_quote_provider.py:39`).
- The quote provider exposes sanitized diagnostics without network calls through
  `get_rotation_radar_provider_diagnostics()`
  (`src/services/rotation_radar_quote_provider.py:181-194`).
- The live smoke entry, if used in a later implementation task, is already
  bounded to the stable ETF probe symbols and does not need new symbols or a
  new provider path (`src/services/rotation_radar_quote_provider.py:197-220`).
- Rotation Radar records provider order, configured-provider status, configured
  feed, failed symbols, yfinance provider status, coverage, and source
  authority diagnostics in quote-provider metadata
  (`src/services/rotation_radar_quote_provider.py:1617-1677`).

## Stable ETF probe contract

### Probe set

- `SPY`: broad US large-cap benchmark and ETF leadership spine member
  (`src/services/rotation_radar_quote_provider.py:42-43`,
  `src/services/market_rotation_radar_service.py:53-54`).
- `QQQ`: large-cap growth / Nasdaq benchmark and ETF leadership spine member
  (`src/services/rotation_radar_quote_provider.py:42-43`,
  `src/services/market_rotation_radar_service.py:53-54`).
- `IWM`: small-cap benchmark and ETF leadership spine member
  (`src/services/rotation_radar_quote_provider.py:42-43`,
  `src/services/market_rotation_radar_service.py:53-54`).
- `SMH`: semiconductor proxy used in the leadership spine
  (`src/services/rotation_radar_quote_provider.py:42-43`,
  `src/services/market_rotation_radar_service.py:54-60`).
- `SOXX`: second semiconductor proxy used to avoid single-ETF dependence in the
  leadership spine (`src/services/rotation_radar_quote_provider.py:42-43`,
  `src/services/market_rotation_radar_service.py:54-60`).
- `IGV`: software proxy used in the leadership spine
  (`src/services/rotation_radar_quote_provider.py:42-43`,
  `src/services/market_rotation_radar_service.py:54-60`).

### Probe behavior

- The configured-provider probe first intersects requested symbols with the
  stable probe set; only if none are present does it fall back to the caller's
  broader symbol list (`src/services/rotation_radar_quote_provider.py:860-878`).
- The blueprint already defines the same six ETFs as the smallest safe starting
  set for T-1764-C and says expansion should wait for feed entitlement,
  freshness, coverage, and source-authority gates
  (`docs/data/market-source-activation-blueprint.md:30-34`,
  `docs/data/market-source-activation-blueprint.md:230-233`).

## Source-authority boundary

- Alpaca credentials are normalized as a `key_secret` bundle with `key_id`,
  `secret_key`, `data_feed`, `credential_source`, `is_configured`,
  `is_partial`, and `missing_fields`
  (`data_provider/provider_credentials.py:90-130`,
  `data_provider/provider_credentials.py:164-180`).
- Credential source is intentionally coarse-grained:
  `control_plane`, `env`, `config`, `unavailable`, or `unknown`
  (`data_provider/provider_credentials.py:53-69`).
- Rotation Radar maps missing credential field identifiers to env-field names
  and exposes them as sanitized diagnostics; no secret values are read into the
  report artifact (`src/services/rotation_radar_quote_provider.py:1028-1057`).
- Source authority is denied whenever yfinance fallback is used, or when the
  effective source/sourceType is in the yfinance proxy allowlist
  (`src/services/rotation_radar_quote_provider.py:1693-1739`).
- The service repeats the same rule when projecting source authority at the
  radar payload layer: yfinance/proxy evidence is route-rejected and receives
  `source_authority_router_rejected`
  (`src/services/market_rotation_radar_service.py:980-1030`).
- Therefore T-1764-C can document and test authority gates, but must not relax
  the current rule that yfinance/proxy data is not scoring-authoritative.

## Freshness and coverage boundary

- Rotation Radar uses 5m, 15m, 60m, and 1d windows for configured-provider
  coverage (`src/services/rotation_radar_quote_provider.py:57-65`).
- Per-window request results already track requested symbol count, success
  count, failure count, failure classes, timed-out symbols, empty-response
  symbols, and whether the minimum required success ratio is fulfilled
  (`src/services/rotation_radar_quote_provider.py:966-989`).
- Base configured-provider metadata already reports:
  `credentialsPresent`, `credentialFieldsMissing`, `configuredProviderFeed`,
  `feedEntitlementStatus`, and whether the provider was constructed
  (`src/services/rotation_radar_quote_provider.py:1028-1057`).
- The activation blockers list already includes credential, entitlement,
  interval mapping, market session, timeout, empty response, short-window
  coverage, and symbol coverage blockers
  (`src/services/rotation_radar_quote_provider.py:110-131`).
- The blueprint states T-1764-C should only exit when configured-provider
  coverage and freshness pass, while yfinance fallback remains non-score-grade
  (`docs/data/market-source-activation-blueprint.md:230-233`).

## Fallback/proxy boundary

- Rotation Radar marks yfinance as `unofficial_public_api` / delayed proxy and
  Alpaca as `broker_authorized` / configured tier
  (`src/services/rotation_radar_quote_provider.py:30-38`).
- Proxy/fallback evidence is explicitly forbidden from claiming reliable
  authoritative provenance; yfinance proxy and ETF price proxy as fund-flow
  evidence both have dedicated forbidden reason codes
  (`src/services/market_rotation_radar_service.py:94-96`,
  `src/services/market_rotation_radar_service.py:159-164`,
  `src/services/market_rotation_radar_service.py:2568-2576`).
- The rotation docs state that if credentials, entitlement, symbol data, or
  provider budget are unavailable, the provider falls back to degraded yfinance
  daily/proxy evidence only and must not synthesize intraday windows or mark
  fallback/static data live (`docs/rotation/README.md:36-45`).
- The evidence-readiness matrix also keeps provider/runtime wiring and source
  authority claims deferred unless a separately scoped protected-domain task
  opens that domain (`docs/data-reliability/evidence-readiness-matrix.md:9-18`).

## Rotation headline eligibility boundary

- Headline ranking warnings explicitly say that only real quote-backed themes
  can rank in headline lanes; fallback/static/taxonomy-only themes remain in
  observation lists (`src/services/market_rotation_radar_service.py:85-87`).
- Headline summary policy keeps fallback/static/taxonomy-only/synthetic/
  unavailable evidence visible but excluded from headline ranking and strong
  conclusions (`src/services/market_rotation_radar_service.py:4576-4581`).
- A theme is headline ranked only when all three conditions are true:
  `rankEligible`, `headlineEligible`, and `rankingLane == "headline"`
  (`src/services/market_rotation_radar_service.py:4596-4602`).
- The rotation docs state that headline lanes may be consumed only when summary
  items expose `rankEligible: true`, `headlineEligible: true`, and
  `rankingLane: "headline"`, while fallback/static/taxonomy-only themes stay in
  observation/taxonomy lanes (`docs/rotation/README.md:21-30`).
- T-1764-C must not change these gates. It can only inventory what quote
  evidence must satisfy before later implementation work uses them.

## Credential/feed entitlement checklist without secret values

- Confirm whether Alpaca credentials are absent, partial, or configured via
  `ProviderCredentialBundle.is_configured`, `.is_partial`, and
  `.missing_fields` (`data_provider/provider_credentials.py:107-130`).
- Record the configured feed value from `alpaca_data_feed`; default remains
  `iex` when unset (`data_provider/provider_credentials.py:164-180`).
- Record only the coarse credential source class:
  `control_plane`, `env`, `config`, `unavailable`, or `unknown`
  (`data_provider/provider_credentials.py:53-69`).
- Use sanitized Rotation Radar diagnostics for:
  `credentialFieldsMissing`, `configuredProviderFeed`,
  `feedEntitlementStatus`, `requestWindowResults`, `activationBlocker`, and
  `minimumActivationCoverageMet`
  (`src/services/rotation_radar_quote_provider.py:1028-1057`,
  `src/services/rotation_radar_quote_provider.py:1060-1105`,
  `src/services/rotation_radar_quote_provider.py:1634-1650`).
- Do not read, print, snapshot, compare, or log raw `ALPACA_API_KEY_ID` or
  `ALPACA_API_SECRET_KEY` values.

## Proposed T-1764-C implementation plan

1. Keep T-1764-C scoped to Rotation Radar quote-boundary inventory and focused
   offline tests/docs only.
2. Reuse the existing stable ETF probe set
   `SPY`, `QQQ`, `IWM`, `SMH`, `SOXX`, `IGV`; do not expand the probe set until
   the configured-provider gate is proven on that bounded spine.
3. Add or refine docs/tests around:
   configured-provider diagnostics, source-authority rejection for yfinance,
   and headline-lane exclusion for fallback/static/taxonomy-only evidence.
4. Do not change provider order, cache semantics, source-authority router
   logic, headline eligibility, or consumer wording.
5. If the work reveals a need to modify shared readiness diagnostics, official
   macro, Market Overview macro/rates/Fed liquidity, or Liquidity Monitor
   files, stop and hand the dependency back to T-1764-B.

## Tests to run later

- `python -m pytest -q tests/test_market_rotation_radar_service.py`
- `python -m pytest -q tests/api/test_market_rotation_radar.py`
- `python -m pytest -q tests/test_provider_credentials.py`
- `python -m pytest -q tests/test_data_fetcher_manager_alpaca.py`
- `python -m pytest -q tests/test_yfinance_us_indices.py tests/test_yfinance_symbol_boundary.py`
- Optional regression proof for generic provider ordering semantics:
  `python -m pytest -q tests/api/test_provider_fallback.py`

These are the existing tests most directly aligned to the T-1764-C boundary:

- bounded ETF authority fixture and authority spine expectations:
  `tests/test_market_rotation_radar_service.py:139-190`,
  `tests/api/test_market_rotation_radar.py:122-172`
- sanitized consumer/admin diagnostic separation:
  `tests/test_market_rotation_radar_service.py:225-239`,
  `tests/api/test_market_rotation_radar.py:183-197`
- yfinance fallback cannot satisfy configured Alpaca windows:
  `tests/test_market_rotation_radar_service.py:2332-2362`
- missing/partial credential diagnostics:
  `tests/test_market_rotation_radar_service.py:2386-2456`,
  `tests/test_provider_credentials.py:25-48`
- entitlement / coverage blockers and authority denial:
  `tests/test_market_rotation_radar_service.py:2646-2667`,
  `tests/test_market_rotation_radar_service.py:2835-2845`
- stable ETF leadership authority spine behavior:
  `tests/test_market_rotation_radar_service.py:3660-3741`,
  `tests/api/test_market_rotation_radar.py:909-1150`
- shared US quote routing outside Rotation Radar:
  `tests/test_data_fetcher_manager_alpaca.py:51-117`
- pure yfinance index boundary:
  `tests/test_yfinance_symbol_boundary.py:25-54`,
  `tests/test_yfinance_us_indices.py:47-98`

## Files allowed later

Later T-1764-C implementation work may safely start in these files if it
remains within docs/tests or narrow Rotation Radar diagnostics:

- `docs/data/market-source-activation-t1764c-quote-boundary-inventory.md`
- `docs/data/market-source-activation-blueprint.md`
- `docs/rotation/README.md`
- `src/services/rotation_radar_quote_provider.py`
- `src/services/market_rotation_radar_service.py`
- `data_provider/provider_credentials.py`
- `tests/test_market_rotation_radar_service.py`
- `tests/api/test_market_rotation_radar.py`
- `apps/dsa-web/src/api/__tests__/marketRotation.test.ts`
- `tests/test_provider_credentials.py`
- `tests/test_data_fetcher_manager_alpaca.py`
- `tests/test_yfinance_us_indices.py`
- `tests/test_yfinance_symbol_boundary.py`
- `tests/api/test_provider_fallback.py`

Allowed later means "inspect first and touch only if required by T-1764-C's
final approved scope." It does not authorize provider-order, cache, or
headline-policy changes.

## Files outside T-1764-C quote scope unless explicitly opened later

Do not edit these files from T-1764-C because they are official macro,
Market Overview macro/rates/Fed liquidity, Liquidity Monitor, or shared
readiness boundaries outside the quote-activation scope. T-1764-B has landed,
but these files still require a separately approved task before T-1764-C may
touch them:

- `src/services/official_macro_transport.py`
- `src/services/market_overview_service.py`
- `src/services/liquidity_monitor_service.py`
- `src/services/market_data_readiness_diagnostics.py`
- `tests/test_liquidity_monitor_service.py`
- `tests/api/test_liquidity_monitor.py`
- `apps/dsa-web/src/api/__tests__/liquidityMonitor.test.ts`
- `apps/dsa-web/src/api/liquidityMonitor.ts`
- `docs/data-reliability/evidence-readiness-matrix.md`

Also treat these as blocked for T-1764-C because changing them would shift
shared runtime or routing behavior outside the task boundary:

- `data_provider/base.py`
- `data_provider/alpaca_fetcher.py`
- `src/services/data_source_router.py`
- `src/services/data_source_router_diagnostics.py`

If T-1764-C needs any of those changes, stop and report the dependency instead
of editing.

## Risks and rollback

### Risks

- Shared `data_provider/base.py` still treats US index realtime quotes as
  yfinance-only, so T-1764-C must avoid over-generalizing Rotation Radar's
  Alpaca-first path into a repo-wide quote-routing claim.
- The stable ETF probe is a bounded authority spine, not approval to promote
  ETF proxy or yfinance proxy evidence into real fund-flow or score-grade use.
- Rotation Radar tests already lock many authority and fallback boundaries. A
  later implementation task that tries to change runtime semantics instead of
  documenting or proving the current gate will likely collide with those tests.
- T-1764-B owns nearby macro/liquidity/readiness surfaces. Crossing into those
  files would create unnecessary rebase/conflict risk and violate the dependency
  boundary.

### Rollback

Current docs-only rollback:

```bash
git revert <commit>
```
