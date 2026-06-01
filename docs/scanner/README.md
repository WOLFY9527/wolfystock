# WolfyStock Scanner Docs

Status: current scanner/watchlist domain entry point.

Use this lane before changing market scanner behavior, watchlist scanner
surfaces, candidate scoring, evidence packets, scanner AI interpretation cache,
export labels, or scanner frontend route hierarchy.

## Current Authority

- [Market Scanner Guide](../market-scanner.md)
- [Scanner Export Label Policy](../product/wolfystock-scanner-export-label-policy.md)
- [Scanner AI Interpretation Cache Design](../audits/scanner-ai-interpretation-cache-design.md)
- [Provider/Data/Options Index](../audits/index-provider-data-options.md)
- [Frontend Visual System](../frontend/visual-system.md)
- [Frontend Validation Playbook](../frontend/validation-playbook.md)

## Current Rules

- Scanner pages should lead with candidate rows/table and selected-candidate
  evidence, not filters or raw diagnostics.
- Candidate explanations should expose why the candidate appeared, main risk,
  data readiness, and a safe observation step.
- Provider, mock, fallback, generated/failed counts, and raw diagnostics are
  secondary details by default.
- Consumer-safe scanner/watchlist projections may add shared
  `investorSignal`/`investor_signal` vocabulary sidecars, but they must stay
  observation-only, fail closed on missing authority, and never expose provider
  observations or alter scoring/ranking semantics.
- Scoring and ranking semantics are protected runtime behavior; UI/docs changes
  must not imply score changes unless the task explicitly scopes them.
