# Stock Quote Freshness API Contract

Date: 2026-05-28
Mode: docs-only API contract note. No runtime code, schemas, routes, services,
providers, tests, frontend, MarketCache, scanner, portfolio, broker/order,
auth/RBAC, backtest, or Options behavior changed.

## Purpose

This note documents the response metadata contract for
`GET /api/v1/stocks/{stock_code}/quote` after T-606.

The goal is to keep future backend, frontend, and agent work from treating
server-side `update_time` as provider market-data freshness or as proof that a
quote is live/tradeable.

## Contract Summary

The endpoint still returns existing quote fields for backward compatibility.
Freshness and provenance fields are additive metadata only. They do not change
provider routing, cache behavior, or endpoint semantics.

Field semantics:

- `update_time`: compatibility field for when the server observed/packaged the
  quote response. It is not, by itself, market-data freshness evidence.
- `marketTimestamp` / `market_timestamp`: provider market-data timestamp when
  the upstream source reports one.
- `observedAt` / `observed_at`: service observation time for the quote payload.
- `source`: bounded provider/source label.
- `sourceType` / `source_type`: classification such as `live`, `fallback`,
  `synthetic`, or `unavailable` style source path.
- `freshness`: bounded status such as `live`, `fallback`, `synthetic`, `stale`,
  or `partial`.
- `isFallback`, `isStale`, `isPartial`, `isSynthetic`: explicit boolean guards
  for the limiting freshness state.
- `sourceConfidence`: optional structured provenance/freshness metadata for
  future UI/agent consumption.

## Required Interpretation Rules

- A current `update_time` alone must not be displayed or interpreted as "live
  quote", "fresh market data", or tradeable evidence.
- If `marketTimestamp` is missing, older than `observedAt`, or the freshness
  flags say fallback/stale/partial/synthetic, consumers must treat the quote as
  limited by that metadata even when `update_time` is current.
- Fallback, placeholder, synthetic, or unavailable quote paths must not be
  displayed as live/fresh only because the response was generated recently.
- `source` is a label for provenance disclosure, not an authority upgrade and
  not proof that the provider is decision-grade.

## Backward Compatibility

- Existing consumers may continue using legacy fields, including
  `update_time`.
- New freshness/source fields are additive and backward-compatible.
- New UI, API clients, and agents should prefer market/source metadata such as
  `marketTimestamp`, `observedAt`, `freshness`, state booleans, and
  `sourceConfidence` when deciding how to label quote quality.

## Forbidden Interpretations

- `update_time` alone means the quote is live.
- Fallback/placeholder/synthetic/unavailable quote output is tradeable or live
  evidence.
- `source` label equals provider authority.
- Freshness metadata changes provider routing, cache policy, or live-call
  behavior.

## Safe Future Usage

- Frontend freshness badges may consume these optional fields later, but should
  key off market/source metadata instead of server `update_time` alone.
- A future `StockEvidencePacket` bridge may reuse the same metadata, but that
  bridge remains optional and is not implied by this contract note.
- This contract does not imply provider routing changes, MarketCache changes,
  source-order changes, or any new runtime integration.

## Practical UI/Agent Rule

If a consumer needs a single safe rule:

- Prefer `marketTimestamp` plus `freshness`/state booleans for market-data
  recency.
- Use `observedAt` as server observation context.
- Treat `update_time` as compatibility metadata only.
