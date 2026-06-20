# Symbol Research Packet Contract

Status: DATA-003 backend contract proposal and first implementation target.

This document defines the minimum symbol research packet needed by Stock Detail
and Watchlist. The packet is a data-readiness contract, not a UI copy strategy
and not a provider integration plan.

## 1. Packet purpose

The symbol research packet gives consumer surfaces one backend-owned answer to:

- who the symbol is;
- which market it belongs to;
- which research data families are present;
- which data families are absent, stale, or not integrated;
- whether the symbol is ready for follow-up research;
- the next data action needed before the product can present a fuller stock
  view.

The packet prevents Stock Detail and Watchlist from inferring readiness from
scattered quote, scanner, structure, evidence, and diagnostic payloads. It must
use existing data only, fail closed when data is absent, and never make missing
data look complete.

## 2. JSON shape

```json
{
  "symbol": "AAPL",
  "market": "us",
  "identity": {
    "name": null,
    "exchange": null,
    "sector": null,
    "industry": null
  },
  "quote": {
    "state": "available",
    "price": 214.55,
    "changePercent": 1.11,
    "asOf": "2026-05-28T09:30:00Z"
  },
  "history": {
    "state": "available",
    "bars": 90,
    "period": "daily",
    "asOf": "2026-05-28"
  },
  "structure": {
    "state": "available",
    "label": "breakout",
    "confidence": "medium",
    "asOf": null
  },
  "fundamentals": {
    "state": "not_integrated",
    "fieldsAvailable": []
  },
  "events": {
    "state": "not_integrated",
    "latest": []
  },
  "peer": {
    "state": "missing",
    "benchmark": null
  },
  "missingData": [
    "fundamentals",
    "filing_event_catalyst",
    "peer_benchmark"
  ],
  "researchStatus": "partial",
  "nextDataAction": "Add fundamentals, filing/event/catalyst, and peer evidence before marking the packet ready.",
  "observationOnly": true,
  "decisionGrade": false,
  "noAdviceDisclosure": "Observation-only research packet; no personalized action instruction."
}
```

Allowed state values:

- `quote.state`: `available`, `missing`, `stale`, `unknown`
- `history.state`: `available`, `missing`, `stale`, `unknown`
- `structure.state`: `available`, `insufficient`, `missing`, `unknown`
- `fundamentals.state`: `available`, `missing`, `not_integrated`, `unknown`
- `events.state`: `available`, `missing`, `not_integrated`, `unknown`
- `peer.state`: `available`, `insufficient`, `missing`, `unknown`
- `researchStatus`: `ready`, `partial`, `blocked`, `unknown`

## 3. Fields and meaning

| Field | Meaning |
| --- | --- |
| `symbol` | Normalized symbol used by backend stock services. |
| `market` | Consumer market code, currently `cn`, `hk`, `us`, or `unknown`. |
| `identity` | Non-diagnostic identity facts. Unknown fields remain `null`. |
| `quote` | Latest quote availability and safe price fields. It does not expose provider/source diagnostics. |
| `history` | Daily OHLCV availability summary. It reports count and latest bar date, not raw rows. |
| `structure` | Observation-only structure analysis availability from existing structure service. |
| `fundamentals` | Fundamental field coverage, if existing evidence payloads expose a safe summary. |
| `events` | Filing, event, or catalyst evidence coverage, if existing evidence payloads expose safe records. |
| `peer` | Peer or benchmark coverage from local peer/structure evidence. |
| `missingData` | Stable, consumer-safe data-family identifiers that are missing, stale, or not integrated. |
| `researchStatus` | Overall readiness derived from family states. It must be conservative. |
| `nextDataAction` | One data action, not a trading instruction. |
| `observationOnly` | Always `true` for this packet. |
| `decisionGrade` | Always `false` for this packet. |
| `noAdviceDisclosure` | Concise boundary string for downstream consumers. |

## 4. Source candidates for each field

| Packet field | Source candidates |
| --- | --- |
| `symbol`, `market` | `validate_consumer_symbol_precheck`, route parameter, optional market query, canonical symbol utilities. |
| `identity.name` | `StockService.validate_ticker_exists`, `StockService.get_realtime_quote`, existing evidence item metadata when safe. |
| `identity.exchange`, `identity.sector`, `identity.industry` | Existing profile/fundamental evidence only if already present and consumer-safe; otherwise `null`. |
| `quote` | `StockService.get_realtime_quote`. Placeholder, synthetic, fallback-only, stale, or missing-price payloads cannot become `available`. |
| `history` | `StockService.get_history_data(period="daily")`. Empty or unavailable rows become `missing`; degraded/cached/fallback rows become `stale`. |
| `structure` | `StockStructureDecisionService.get_structure_decision`. It remains observation-only and inherits data-quality limits. |
| `fundamentals` | `StockEvidenceService.get_stock_evidence` safe `stockEvidencePacket.fundamentalsSummary` or item `fundamental` coverage. |
| `events` | Existing `news` and `secFilingEvidence` evidence blocks when they expose safe records. No new provider is authorized here. |
| `peer` | `peerCorrelationSnapshot` from `StockStructureDecisionService`. |
| `missingData`, `researchStatus`, `nextDataAction` | Derived inside the packet projection from the states above. |

## 5. Current code owner for each field

| Packet field | Current owner |
| --- | --- |
| `symbol`, `market` | `src.utils.symbol_validation`, `src.utils.symbol_normalization`, `api/v1/endpoints/stocks.py` |
| `identity` | `src/services/stock_service.py` plus future safe profile evidence owner |
| `quote` | `src/services/stock_service.py`, projected by `api/v1/endpoints/stocks.py` |
| `history` | `src/services/stock_service.py`, projected by `api/v1/endpoints/stocks.py` |
| `structure` | `src/services/stock_structure_decision_service.py` |
| `fundamentals` | `src/services/agent_stock_evidence_service.py`, `api/v1/schemas/stocks.py` safe evidence schemas |
| `events` | `src/services/agent_stock_evidence_service.py` and existing single-stock evidence helpers |
| `peer` | `src/services/stock_structure_decision_service.py` local peer correlation path |
| `missingData`, `researchStatus`, `nextDataAction` | New packet projection owner in the stock API/service boundary |
| Watchlist consumption | `src/services/watchlist_service.py`, `src/services/watchlist_research_overlay_service.py`, `api/v1/endpoints/watchlist.py` |
| Stock Detail consumption | `api/v1/endpoints/stocks.py`, `apps/dsa-web/src/api/stocks.ts`, `StockStructureDecisionPage` when UI wiring is later scoped |

## 6. Missing provider/data blocker for each field

| Packet field | Current blocker |
| --- | --- |
| `identity.exchange`, `identity.sector`, `identity.industry` | No guaranteed safe profile snapshot is integrated into the current stock detail contract. |
| `quote` | Adapter may return no quote, missing timestamp, placeholder, synthetic, fallback, stale, or partial payloads. |
| `history` | Daily OHLCV can be unavailable, local-only, degraded, or aggregation-empty. |
| `structure` | Requires usable daily OHLCV; otherwise confidence remains bounded or missing. |
| `fundamentals` | Fundamentals summary may be absent, partial, stale, or not integrated for the symbol. |
| `events` | Filing/event/catalyst evidence is not guaranteed across markets and must stay empty when not integrated. |
| `peer` | Requires verified local peer group metadata and overlapping local daily OHLCV for peers. |
| `researchStatus` | Cannot be `ready` until required families are available without stale/missing/not-integrated blockers. |

## 7. Freshness requirements

- Quote is `available` only when a real price is present and the quote is not
  synthetic, fallback, stale, or unavailable. A present price with degraded
  freshness is `stale`.
- History is `available` only when daily bars are present and diagnostics do
  not mark the source as unavailable, degraded, fallback, or stale. Present but
  degraded bars are `stale`.
- Structure follows the structure service data-quality status. `available`
  requires available structure inputs; partial or insufficient inputs become
  `insufficient`.
- Fundamentals and events are `available` only when existing evidence payloads
  expose safe non-empty fields or records.
- Peer data is `available` only when peer evidence exists; otherwise it is
  `insufficient` or `missing`.
- The packet should use ISO timestamps or dates already reported by upstream
  service payloads. It must not invent timestamps.

## 8. Fail-closed behavior

- Unsupported, ambiguous, invalid, or unverified symbols return a blocked packet
  instead of a fabricated research packet.
- Missing data stays `missing` or `not_integrated`; placeholder data does not
  become available.
- Degraded data lowers the relevant family state and adds a `missingData` entry.
- The endpoint must not expose provider, cache, runtime, request, trace, schema,
  source-authority, or raw diagnostic fields in the consumer packet.
- The endpoint must not call paid providers unless they are already used by the
  existing stock services for the same data family.
- Existing source and evidence gates remain intact.

## 9. No-advice boundary

The packet is a research-readiness and data-coverage object. It must not carry
personalized action instructions, target/stop levels, position sizing, or
recommendations. Structure labels, price facts, evidence gaps, and next data
actions are allowed only as observation-only research context.

`nextDataAction` must name a data action such as refreshing quote/history,
adding fundamentals, adding filing/event/catalyst evidence, or adding peer
metadata. It must never instruct the user to trade.

## 10. How Watchlist should consume it

Watchlist should consume the packet as a row-level enrichment boundary:

- show `quote.price`, `quote.changePercent`, and `quote.asOf` only when
  `quote.state` is `available` or explicitly degraded in a compact way;
- show `researchStatus` instead of deriving readiness from scanner/backtest
  diagnostics;
- show one compact `missingData` summary per row or per page group;
- use `nextDataAction` for follow-up research workflow entry points;
- link to Stock Detail when `researchStatus` is `ready` or `partial`;
- keep provider/source/cache/runtime details out of the default row.

Watchlist should not infer quote freshness or research readiness by combining
scanner score fields, backtest timestamps, and overlay diagnostics on the
frontend.

## 11. How Stock Detail should consume it

Stock Detail should consume the packet before or alongside the existing
structure-decision response:

- lead with identity, quote, history, and structure availability;
- render fundamentals, events, and peer sections only when their packet state
  is useful or when a compact missing-data summary is needed;
- show one missing-data summary, not repeated module-level diagnostics;
- route the user to the next data action when `researchStatus` is `blocked` or
  `partial`;
- continue to treat structure analysis as observation-only and not
  decision-grade.

Stock Detail should not assemble research readiness from separate quote,
history, evidence, and structure calls in the page layer.

## 12. Next implementation steps

1. Add an additive stock API contract:
   `GET /api/v1/stocks/{stock_code}/research-packet`.
2. Add Pydantic response models in the stock schema module with the state enums
   listed above.
3. Build the packet from existing `StockService`, `StockStructureDecisionService`,
   and `StockEvidenceService` outputs only.
4. Add API contract tests for available quote/history/structure plus explicit
   fundamentals/events/peer gaps.
5. Add fail-closed tests for placeholder quote, unavailable history, missing
   evidence, and forbidden recommendation vocabulary.
6. Optionally add frontend API types in `apps/dsa-web/src/api/stocks.ts` once a
   UI task is explicitly scoped.
7. Later Watchlist and Stock Detail UI tasks should consume this packet instead
   of guessing readiness from scattered diagnostics.
