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
