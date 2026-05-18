# WolfyStock Liquidity Docs

Status: current liquidity domain entry point.

Use this lane before changing liquidity monitor UI, liquidity score display,
signal tables, source/risk rails, or liquidity-related freshness disclosure.

## Current Authority

- [Provider And Data Docs](../provider-data/README.md)
- [Frontend Visual System](../frontend/visual-system.md)
- [Frontend Validation Playbook](../frontend/validation-playbook.md)
- [Data Quality User Disclosure Policy](../audits/data-quality-user-disclosure-policy.md)

## Current Rules

- Liquidity pages should lead with liquidity score and signal table.
- Source/risk detail belongs in a bounded rail or disclosure.
- Do not let provider/cache/raw diagnostics become the default primary content.
- Do not imply execution readiness from liquidity evidence without an explicit
  safety-reviewed task.

## Backend Diagnostics

- Liquidity Monitor indicator payloads may include additive
  `coverageDiagnostics` metadata.
- Diagnostics must explain required, fulfilled, and missing inputs; source
  tier; freshness; trust level; score contribution; cap/degradation reason; and
  activation hints.
- Missing, stale, fallback, synthetic, or unavailable inputs must not appear
  live or contribute strong score.
- CN/HK flow, money-market, futures, and proxy indicators must stay explicit
  about unavailable sources unless an existing configured and audited source
  provides real data.
