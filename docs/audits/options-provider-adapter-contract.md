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

## Disabled Live Provider Stubs

Disabled-by-default live adapter stubs now exist for `tradier`, `ibkr`, and `polygon`. They implement the same provider interface shape and expose capability metadata, but they do not load credentials, call network APIs, return raw provider payloads, place orders, mutate portfolio state, or participate in global market-provider fallback.

Fixture providers remain the default selection contract. Live provider names are allowed keys only so Options Lab can fail closed with stable sanitized errors:

- `options_provider_disabled`: live provider stubs are globally disabled by default.
- `options_provider_not_enabled`: live stubs are globally allowed in a future config path, but the selected provider is not explicitly enabled.
- `options_provider_credentials_missing`: the selected provider is enabled in a future config path, but credential presence has not been confirmed.

The stub config contract carries only provider keys and booleans. It must not print, serialize, or expose API keys, tokens, secrets, account identifiers, request URLs, raw environment values, or raw provider responses.

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
