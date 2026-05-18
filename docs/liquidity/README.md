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
