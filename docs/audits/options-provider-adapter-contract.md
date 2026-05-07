# Options Provider Adapter Contract

## Scope

This note documents the real-data-ready Options Lab provider contract added before any Tradier, IBKR, or Polygon live integration. The current implementation is fixture-only and must not call live providers, read credentials, place orders, mutate portfolio state, or alter global market-provider fallback behavior.

## Contract

Future adapters must implement `OptionsMarketDataProvider` in `src/services/options_market_data_provider.py`:

- `provider_name`
- `capabilities`
- `get_expirations(symbol)`
- `get_underlying_quote(symbol)`
- `get_chain(symbol, expiration)`

Provider outputs must be sanitized normalized snapshots. Raw provider payloads, request URLs, API keys, tokens, account identifiers, and stack traces must not be returned by Options Lab APIs.

## Normalized Contract Fields

Each option contract consumed by the decision engine must normalize:

- price fields: `bid`, `ask`, `mid`, `last`
- activity fields: `volume`, `openInterest`
- volatility and Greeks: `impliedVolatility`, `delta`, `gamma`, `theta`, `vega` through `greeks`
- contract metadata: `expiration`, `strike`, `side`, `multiplier`
- data provenance: `asOf`, `source`, `freshness`, `providerQuality`, `dataQuality`

Missing provider values must remain missing and degrade data quality. The service must not fabricate Greeks, IV, bid/ask, volume, or OI to make a contract appear tradeable.

## Fixture Providers

The only enabled providers are fixture adapters:

- `synthetic_fixture`: current TEM synthetic fixture, demo-only.
- `delayed_fixture`: real-shaped delayed fixture, not tradeable under current policy.
- `malformed_fixture`: missing IV/Greeks fixture for degradation tests.

## Disabled Live Provider Stubs and Tradier Dry Run

Disabled-by-default live adapter stubs now exist for `tradier`, `ibkr`, and `polygon`. They implement the same provider interface shape and expose capability metadata, but they do not load credentials, call network APIs, return raw provider payloads, place orders, mutate portfolio state, or participate in global market-provider fallback.

Fixture providers remain the default selection contract. Live provider names are allowed keys only so Options Lab can fail closed with stable sanitized errors:

- `options_provider_disabled`: live provider stubs are globally disabled by default.
- `options_provider_not_enabled`: live stubs are globally allowed in a future config path, but the selected provider is not explicitly enabled.
- `options_provider_credentials_missing`: the selected provider is enabled in a future config path, but credential presence has not been confirmed.
- `options_provider_dry_run_not_enabled`: the selected live provider is enabled and credential presence is confirmed, but dry-run mapping is not explicitly enabled.
- `options_provider_payload_unmappable`: a dry-run provider-shaped payload could not be mapped into the normalized contract without exposing raw provider details.

The stub config contract carries only provider keys and booleans. It must not print, serialize, or expose API keys, tokens, secrets, account identifiers, request URLs, raw environment values, or raw provider responses.

Tradier now has a dry-run-only mapping foundation behind `OptionsLiveProviderConfig`. It can map a fixture-like Tradier options-chain shape into the provider-neutral contract for expirations, underlying quote, bid/ask, volume, open interest, IV, and Greeks. Even when explicitly enabled for dry-run, the adapter marks `liveEnabled=false`, `tradeableData=false`, `freshness=delayed_dry_run`, and `dataQuality.tradeable=false`.

Optional `.env.example` knobs document the disabled contract:

- `OPTIONS_LIVE_PROVIDERS_ENABLED=false`
- `OPTIONS_LIVE_PROVIDER_KEYS=tradier`
- `OPTIONS_TRADIER_ENABLED=false`
- `OPTIONS_TRADIER_DRY_RUN_ENABLED=false`
- `TRADIER_API_TOKEN=`

These knobs are a dry-run foundation only. They do not authorize a live Tradier request path, broker/order execution, portfolio mutation, scanner/backtest provider fallback changes, or Options Decision Engine scoring-threshold changes.

## Future Live Adapter Requirements

Before enabling any live provider adapter:

- prove entitlement and field coverage for expirations, chain, bid/ask, last, volume, OI, IV, Greeks, multiplier, and contract symbology;
- provide explicit market-time freshness semantics and stale-data rejection or downgrade rules;
- preserve no raw payload, no credential, and no request URL exposure;
- keep data-quality caps until product policy explicitly allows delayed or provider-specific data to be decision-grade;
- add fixture and mocked-provider tests before credentialed smoke tests;
- document provider-specific gaps such as missing Greeks, delayed OI, option symbology differences, and multiplier/deliverable edge cases;
- keep broker execution, order placement, portfolio mutation, cost ledger, quota, scanner, backtest, MarketCache, and global provider fallback out of adapter enablement unless separately approved.

## Provider-Specific Remaining Work

- Tradier: confirm option chain entitlement, OPRA delay semantics, Greeks/IV coverage, expiration format, and rate-limit handling before any credentialed smoke.
- IBKR: define a read-only market-data session boundary, entitlement checks, contract identifier mapping, multiplier/deliverable handling, pacing limits, and account identifier redaction.
- Polygon: confirm options snapshot/chain endpoint coverage, delayed versus real-time plan behavior, Greeks/IV availability by plan, pagination handling, and request-cost controls.

All three providers still require mocked-provider tests, credentialed smoke design, freshness downgrade policy, data-quality caps, and explicit security review before live integration.
