# WolfyStock Product Audit Docs

Status: current product-audit entry point.

Use this lane when a task references a product-level diagnostic audit,
root-cause map, or evidence-readiness decision that was captured as a
standalone audit doc rather than a codex audit report.

## Current Canonical Audit

- [T-1758 Market Data P0 Root-cause Map](./t1758-market-data-p0-root-cause-map.md):
  current canonical diagnosis of why consumer evidence surfaces (Market
  Overview, Decision Cockpit, Liquidity Monitor, Rotation Radar, Research
  Radar, Home briefing) are not delivering useful consumer evidence. Covers
  endpoint inventory, provider chain, fallback behavior, root-cause map per
  P0 issue, and recommended implementation wave.

## Related Diagnostic Lineage

T-1758 is the first task in the market-data diagnostic lineage. Downstream
tasks that refined the contract live in other docs lanes:

| Task | Title | Canonical doc |
| --- | --- | --- |
| T-1758 | Market Data P0 Root-cause Map | `docs/product-audit/t1758-market-data-p0-root-cause-map.md` |
| T-1761 | Consumer Evidence Readiness Matrix | `docs/data-reliability/evidence-readiness-matrix.md` |
| T-1762 | Liquidity Coverage Contract Reconciliation | `docs/liquidity/README.md` (Backend Diagnostics section) |
| T-1763 | Rotation Radar Consumer Status Quarantine | `docs/rotation/README.md` (Current Rules section) |

## Historical Codex Audit Reports

Point-in-time Codex audit reports that no longer need to live in the active
audit lane are retained under `docs/codex/audits/` (active) and
`docs/codex/audits/archive/` (historical provenance only). They are not
current authority unless a current index or handbook points to them for a
specific question.

## Scope Note

This lane holds standalone product-level diagnostic audits that are not
Codex-process workflow docs (those live in `docs/codex/`) and not
point-in-time audit reports (those live in `docs/audits/`).
