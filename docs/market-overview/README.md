# WolfyStock Market Overview Docs

Status: current market overview domain entry point.

Use this lane before changing broad market state, market freshness disclosure,
market monitor UI, market overview API assumptions, or market overview operator
evidence.

## Current Authority

- [Provider And Data Docs](../provider-data/README.md)
- [Frontend Visual System](../frontend/visual-system.md)
- [Frontend Validation Playbook](../frontend/validation-playbook.md)
- [Data Quality User Disclosure Policy](../audits/data-quality-user-disclosure-policy.md)
- [Provider Data Freshness Reliability Guide](../audits/provider-data-freshness-reliability-guide.md)
- [Market Intelligence Smoke Checklist](./market-intelligence-smoke-checklist.md)

## Current Rules

- The first viewport should answer whether the market state is usable for
  observation, what is partial/stale/unavailable, and which broad risk or
  rotation clue matters.
- `regimeSummary` on `/api/v1/market/temperature` is additive and
  observation-only. It may summarize current market synthesis plus existing
  Liquidity `capitalFlowSignal` and Rotation `rotationFamilyRollup`, but it
  must never promote source authority, score-grade rights, or live provider
  status.
- Rotation `themeFlowSignal.breadthEvidence` may only become explanatory
  `regimeSummary.drivers` or `regimeSummary.nextWatchItems` context. It remains
  a quote-breadth proxy, not real fund-flow evidence, and must not change
  `regimeSummary.label`, confidence, source authority, or score contribution.
- Liquidity `capitalFlowSignal.sourceAssetPressure` may only add bounded
  `regimeSummary.nextWatchItems` context when existing QQQ / IWM proxy rows show
  narrow growth absorption. It remains quote-derived proxy observation, not real
  fund-flow evidence, and must not add drivers or change `regimeSummary.label`,
  confidence, source authority, or score contribution.
- Allowed `regimeSummary.label` values are:
  `risk_on_growth_led`, `risk_on_broad`, `risk_off_defensive`,
  `liquidity_positive`, `liquidity_negative`, `inflation_oil_pressure`,
  `mixed_no_clear_edge`.
- If Liquidity or Rotation observation signals are missing, stale, fallback,
  unavailable, or internally contradictory, `regimeSummary` must fail closed to
  `mixed_no_clear_edge` with blockers, confidence caps, and next watch items.
- Freshness/source detail belongs in a rail or disclosure, not as the primary
  story.
- Partial data should render a degraded but readable state, never a blank page
  or overconfident healthy state.
- Official macro rows that come from FRED or Treasury must keep
  `official_public` provenance and delayed/stale semantics; daily or monthly
  official releases must never be projected as realtime.
- Current backend macro coverage includes Treasury curve tenors, SOFR, VIX
  close, effective fed funds, CPI YoY, PPI YoY, and the observation-only
  credit-spread proxy. When monthly inflation history is insufficient, the row
  must stay explicitly unavailable rather than falling back to a fake fresh
  reading.
