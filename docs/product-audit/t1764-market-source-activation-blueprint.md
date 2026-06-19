# T-1764 Market Source Activation Blueprint

Status: READY

This product-audit note records the T-1764 planning outcome and points to the
implementation-ready blueprint:

- `docs/data/market-source-activation-blueprint.md`

## Outcome

The first activation wave should proceed in this order:

1. Official VIX / volatility.
2. Macro / rates / Fed liquidity.
3. US index / ETF quote coverage, then sector/rotation quote coverage on the
   same credential/feed boundary.

The blueprint keeps real funds-flow, US breadth/internals, options gamma/dealer
exposure, and CN market data outside the first wave because they require
stronger entitlement, coverage, methodology, or manual-review proof.

## Scope Boundary

This artifact is docs-only. It does not change product/runtime code, provider
adapters, provider order, cache behavior, credentials, database state, scanner
state, broker sync, pricing, storage, auth, sessions, RBAC, accounting,
backtest, or LLM behavior.

## Validation Plan

Current docs-only validation:

```bash
git diff --check origin/main...HEAD
git diff --check
bash scripts/release_secret_scan.sh --base-ref origin/main
```

Use grep review on the two T-1764 Markdown files for no-advice wording and
sensitive diagnostic leakage if no docs lint command exists.
