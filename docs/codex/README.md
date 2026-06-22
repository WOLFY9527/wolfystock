# WolfyStock Codex Docs

Status: active Codex-process navigation.

Use this directory for current Codex workflow rules, prompt contracts, frontend
validation policy, and reusable task templates.

## Core Process Docs

- `WOLFYSTOCK_CODEX_STANDARD_GUARD.md`
- `WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md`
- `WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md`
- `WOLFYSTOCK_CODEX_VALIDATION_MATRIX.md`
- `WOLFYSTOCK_CODEX_MODEL_ROUTING.md`
- `WOLFYSTOCK_PROMPT_CONTEXT_INDEX.md`
- `WOLFYSTOCK_CODEX_EXECUTION_POLICY.md`
- `WOLFYSTOCK_SHARED_MAIN_WORKTREE_PROTOCOL.md`

## Canonical Project Documentation Index

Use these pointers when a task touches market-data surfaces, evidence readiness,
provider diagnostics, or consumer-safety boundaries. They are the current
canonical diagnostic lineage and cross-domain entry points.

### Market-Data Diagnostic Lineage (T-1758 → T-1761 → T-1762 → T-1763)

| Task | Title | Canonical doc or evidence | Status |
| --- | --- | --- | --- |
| T-1758 | Market Data P0 Root-cause Map | `docs/product-audit/t1758-market-data-p0-root-cause-map.md` | LANDED — current canonical root-cause map for consumer evidence gaps |
| T-1761 | Consumer Evidence Readiness Matrix | `docs/data-reliability/evidence-readiness-matrix.md` | LANDED — stop/go matrix for evidence surfaces; tests/contracts ready does not equal implementation readiness |
| T-1762 | Liquidity Coverage Contract Reconciliation | `docs/liquidity/README.md` (Backend Diagnostics section) | LANDED — reconciled Liquidity denominator: 12 families × 39 required input slots for coverage; 49 is score-weight budget only |
| T-1763 | Rotation Radar Consumer Status Quarantine | `docs/rotation/README.md` (Current Rules section) | LANDED — locked consumer evidence snapshot and theme-flow signal as observation-only |

### Cross-Domain Entry Points

| Domain | Current canonical entry |
| --- | --- |
| Market-data P0 diagnosis | `docs/product-audit/t1758-market-data-p0-root-cause-map.md` |
| Evidence readiness and stop/go | `docs/data-reliability/evidence-readiness-matrix.md` |
| Data coverage contract | `docs/data-reliability/data-coverage-matrix-v1.md` |
| Provider source-confidence contract | `docs/data-reliability/provider-source-confidence-contract.md` |
| Liquidity coverage and scoring | `docs/liquidity/README.md` |
| Rotation consumer evidence and theme-flow | `docs/rotation/README.md` |
| Frontend IA, route taxonomy, validation | `docs/frontend/README.md` |
| No-advice and consumer-safety guards | `docs/codex/NO_ADVICE_REGRESSION_GUARDS.md` |
| Provider budget and routing rules | `docs/codex/WOLFYSTOCK_PROVIDER_BUDGET_AND_ROUTING_RULES.md` |
| Backend protected domains | `docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md` |
| General docs navigation | `docs/DOCS_INDEX.md` |

### Liquidity Denominator Note

The public contract exposed by T-1762 reports required-input coverage as 12
indicator families and 39 named required input slots from
`LIQUIDITY_INDICATOR_REQUIRED_INPUTS`. The numeric value 49 is a separate
score-weight budget (`score.possibleIndicatorWeight` /
`coverageContract.scoreWeightBudget`), not an indicator-family count and not
the required-input denominator. Any doc or prompt wording like
"1 of 49 indicators" is stale; use required input coverage for coverage copy
and score-weight budget for scoring copy.

## Prompt And Task Authoring

- `WOLFYSTOCK_CODEX_COMPACT_PROMPT_PROTOCOL.md`
- `WOLFYSTOCK_CODEX_COMPACT_TASK_EXAMPLES.md`
- `WOLFYSTOCK_CODEX_TASK_TEMPLATES.md`

## Protected-Domain Guidance

- `WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md`
- `WOLFYSTOCK_PROVIDER_BUDGET_AND_ROUTING_RULES.md`
- `WOLFYSTOCK_BACKTEST_UNIVERSE_RULES.md`

`WOLFYSTOCK_CODEX_EXECUTION_POLICY.md` is a compact summary only. The core operational source for Codex tasks is still `WOLFYSTOCK_CODEX_STANDARD_GUARD.md` plus `WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md`.

Frontend implementation, route taxonomy, visual system, primitive policy, and
browser-evidence rules now live in `../frontend/README.md`.

Historical Codex audit reports and retired goal-progress notes live under
`../archive/codex/`. `docs/codex/` should contain durable workflow, prompt,
validation, protected-domain, surface-map, and reporting references only.
