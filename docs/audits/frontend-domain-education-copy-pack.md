# WolfyStock Frontend Domain Education Copy Pack

Date: 2026-05-09
Branch checked: `main`
Mode: domain copy system. No production page files, backend logic, AI prompts,
scanner/provider/backtest/portfolio calculations, launch acceptance files, or
runtime configuration were changed.

## Purpose

This copy pack defines reusable beginner-friendly Chinese explanations for
advanced market-analysis concepts. The entries are designed for future UI
integration as tooltips, disclosures, glossary panels, onboarding notes, or
evidence explanations.

The wording is intentionally educational and domain-safe:

- It explains concepts and evidence quality.
- It avoids personalized financial advice.
- It avoids order/execution wording.
- It avoids secret-like examples and raw provider/debug jargon.
- It keeps operational concepts understandable without exposing internals.

## Source File

Canonical data source:

```text
apps/dsa-web/src/data/domainEducation.ts
```

Focused validation:

```text
apps/dsa-web/src/data/__tests__/domainEducation.test.ts
```

## Category Counts

| Category | Entries |
| --- | ---: |
| Market regime | 6 |
| Scanner evidence | 6 |
| Watchlist evidence | 6 |
| Options Greeks | 6 |
| Options liquidity | 6 |
| Backtest reliability | 6 |
| Portfolio accounting | 6 |
| Provider/data freshness | 6 |
| Admin/Ops | 6 |
| Risk language | 6 |
| Total | 60 |

## Coverage

The pack includes beginner-safe explanations for the requested concepts:

- Market and technical context: RSI, MACD, moving averages, volume,
  volatility, market breadth.
- Scanner and watchlist evidence: evidence confidence, data readiness,
  confluence, catalysts, relative strength, volume confirmation, review cadence,
  evidence decay, note quality.
- Options education: IV, Delta, Gamma, Theta, Vega, Rho, OI, Bid/Ask, spread,
  liquidity, depth, stale option-chain data.
- Backtest reliability: drawdown, Sharpe, win rate, sample size, overfitting,
  benchmark comparison.
- Portfolio accounting: manual ledger, exposure, cash balance,
  realized/unrealized results, FX impact, reconciliation.
- Provider and operations: delayed data, fallback, provider/source differences,
  cache, stale data, readiness, SLA, circuit breaker, quota, observability,
  readiness gates, audit logs.
- Risk language: non-advice framing, confidence wording, scenario language,
  uncertainty, suitability, and loss-risk disclosure.

## Copy Contract

Each entry contains:

- `id`
- `category`
- `titleZh`
- `shortZh`
- `explainZh`
- `beginnerExampleZh`
- `caveatZh`
- `forbiddenInterpretationsZh`

Length budgets enforced by tests:

- `shortZh`: max 60 characters
- `explainZh`: max 160 characters
- `beginnerExampleZh`: max 120 characters
- `caveatZh`: max 120 characters

Safety checks enforced by tests:

- IDs are unique.
- Categories are restricted to the approved 10 groups.
- Direct trading-advice phrases are rejected.
- Credential-like strings are rejected.

## Integration Guidance

Future page integrations should keep this file as data-only copy and map entries
into existing UI surfaces without changing calculations or backend contracts.
Recommended use:

- Tooltip or disclosure text near technical labels.
- Glossary drawer grouped by category.
- Evidence-detail panels where beginner education is useful.
- Empty-state or degraded-state support text when data quality is limited.

Avoid using the entries as:

- Personalized action recommendations.
- Ranking or scoring logic.
- Runtime provider fallback logic.
- AI prompt content without a separate prompt-safety review.
- Replacement for existing no-advice disclosures.

## Safety Notes

This pack deliberately uses educational language such as “观察”, “复查”,
“证据”, “状态”, and “限制条件”. It does not introduce order CTAs, execution
actions, broker behavior, provider behavior, portfolio accounting behavior, or
backtest-calculation behavior.

Docs and data only. Browser verification is not required until entries are wired
into production pages.
