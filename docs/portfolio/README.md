# WolfyStock Portfolio Docs

Status: current portfolio domain entry point.

Use this lane before changing portfolio holdings, account/ledger behavior,
Phase F evidence, cash/corporate-action/trade provenance, portfolio frontend
hierarchy, or portfolio public-safety wording.

## Current Authority

- [Module Architecture Manual](../architecture/WOLFYSTOCK_MODULE_ARCHITECTURE.md)
- [Phase F Decisions](../architecture/phase-f/decisions.md)
- [Phase F Status](../architecture/phase-f/status.md)
- [Phase F Runbook](../architecture/phase-f/runbook.md)
- [Portfolio Research Smoke Checklist](./portfolio-research-smoke-checklist.md)
- [Backtest / Portfolio Public Safety Audit](../audits/backtest-portfolio-public-safety-audit.md)
- [Frontend Visual System](../frontend/visual-system.md)

## Current Rules

- Portfolio UI leads with holdings, P&L, exposure, FX/read-only sync state, and
  data confidence before manual forms.
- Holding valuation price disclosure must distinguish live quote snapshots,
  broker-sync snapshots, and avg-cost fallback estimates without changing
  ledger/accounting math or mutation behavior.
- Manual mutations are ledger/accounting records, not broker order execution.
- Avoid default launch copy such as `买入`, `卖出`, `提交交易`, `下单`, or
  `立即交易` unless explicitly safety-reviewed.
- Portfolio accounting and public-safety semantics are protected runtime
  behavior.
