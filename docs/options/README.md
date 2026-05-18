# WolfyStock Options Docs

Status: current Options Lab domain entry point.

Use this lane before changing options provider adapters, option-chain
readiness, Greeks display, Options Lab UI, scenario/strategy copy, or trading
no-advice policy.

## Current Authority

- [Options Provider Adapter Contract](../audits/options-provider-adapter-contract.md)
- [Options Lab Phase 0 Design](../audits/options-lab-phase0-design.md)
- [Trading No-Advice Product Policy](../audits/trading-no-advice-product-policy.md)
- [Provider/Data/Options Index](../audits/index-provider-data-options.md)
- [Frontend Visual System](../frontend/visual-system.md)

## Current Rules

- Options Lab should start with scenario readiness, data sufficiency, and
  no-advice framing before chain, Greeks, or strategy detail.
- Chain/payoff/Greeks/provider diagnostics should be contained in scroll,
  drawer, disclosure, or bounded rail.
- Rename execution-flavored labels into scenario/readiness language unless
  explicitly safety-reviewed.
- Options provider behavior and adapter semantics are protected runtime
  behavior.
