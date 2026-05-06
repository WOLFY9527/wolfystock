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

Known live provider names `tradier`, `ibkr`, and `polygon` are intentionally disabled and return `options_provider_not_implemented`.

## Future Live Adapter Requirements

Before enabling any live provider adapter:

- prove entitlement and field coverage for expirations, chain, bid/ask, last, volume, OI, IV, Greeks, multiplier, and contract symbology;
- provide explicit market-time freshness semantics and stale-data rejection or downgrade rules;
- preserve no raw payload, no credential, and no request URL exposure;
- keep data-quality caps until product policy explicitly allows delayed or provider-specific data to be decision-grade;
- add fixture and mocked-provider tests before credentialed smoke tests;
- document provider-specific gaps such as missing Greeks, delayed OI, option symbology differences, and multiplier/deliverable edge cases;
- keep broker execution, order placement, portfolio mutation, cost ledger, quota, scanner, backtest, MarketCache, and global provider fallback out of adapter enablement unless separately approved.
