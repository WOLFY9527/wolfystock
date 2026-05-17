# WolfyStock AI Maintenance Manual

This manual is the AI-agent operating guide for maintaining WolfyStock. It is
for Codex workers, review agents, integrators, and humans assigning work.

Use it with:

- [Docs Index](./DOCS_INDEX.md)
- [System Handbook](./WOLFYSTOCK_SYSTEM_HANDBOOK.md)
- [Codex Standard Guard](./codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md)
- [Codex Task Runtime Rules](./codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md)
- [Codex Final Report Template](./codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md)
- [Compact Prompt Protocol](./codex/WOLFYSTOCK_CODEX_COMPACT_PROMPT_PROTOCOL.md)
- [Model Routing](./codex/WOLFYSTOCK_CODEX_MODEL_ROUTING.md)

## Core Maintenance Rule

AI maintenance should reduce ambiguity, not add parallel systems. Before
editing, read the current implementation, the current tests, the current docs,
and the task-specific allowlist. Then make the smallest change that satisfies
the task and prove it with focused validation.

Do not use memory, stale screenshots, older branch notes, old audit reports, or
generated local artifacts as current truth when the repository can be inspected.

## Codex Task Modes

WolfyStock task prompts use stable modes. The mode is part of the contract.

| Mode | Meaning | Default behavior |
| --- | --- | --- |
| `WORKTREE-WORKER` | Execution in an isolated worktree and named branch | Work only in the prompt workspace, keep branch exact, validate, commit, push if requested |
| `WORKTREE-WORKER-DOCS` | Docs-only execution in an isolated worktree | Edit only allowlisted docs, run docs validation, commit/push if requested |
| `SERIAL-MAIN` | One safe task on shared `main` | Work directly in the named repo only when explicitly requested |
| `READ-ONLY-AUDIT` | Audit, inventory, design check, or risk map | Do not edit, create artifacts, stage, commit, or push |
| `REPORT-ONLY` | Create only the requested report artifact | Keep runtime/source untouched; report output is evidence, not approval |

If workspace, branch, mode, or allowed files do not match the prompt, stop and
report the mismatch.

## Model Routing

The surrounding task or Codex UI should choose model/reasoning. Do not bury
model selection inside reusable prompt bodies.

Default routing:

- decision, architecture, or high-risk audit: Codex 5.5 with xhigh reasoning;
- shared infrastructure execution: Codex 5.4 with high reasoning;
- audited bounded execution: Codex 5.4 with high reasoning;
- low-risk docs/test patch: Codex 5.4 with medium reasoning;
- simple read-only inventory: Codex 5.4 with medium reasoning.

Source: [Model Routing](./codex/WOLFYSTOCK_CODEX_MODEL_ROUTING.md).

## Preflight Contract

Execution tasks start by confirming the real repository state:

```bash
pwd
git fetch origin
git status --short --branch
git log --oneline -5
git log --oneline --decorate origin/main..HEAD
git diff --name-only
git diff --cached --name-only
```

Stop if:

- branch or path is wrong;
- staged files already exist before the task starts;
- target files are already dirty and the prompt did not allow that;
- the task requires forbidden branches, forbidden worktrees, dependency
  installation, runtime code, or protected-domain changes outside scope.

Untracked local Codex config may exist. Do not stage it unless the task
explicitly changes Codex config.

## Final Report Contract

Use [Codex Final Report Template](./codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md).
Execution-class success reports should include:

- Task ID and title;
- ledger status;
- actual workspace, branch, and base commit;
- commit hash/message;
- push status;
- files changed;
- what changed and why;
- boundary impact;
- behavior explicitly unchanged;
- validation commands and exact results;
- risks;
- artifact hygiene;
- final git status;
- rollback command.

Docs-only closeout can be concise, but still report docs edited, source docs
referenced, validation, intentionally untouched files, and final status.

## Protected Domains And Stop Conditions

Protected domains are semantic contracts. If a requested docs/test/UI change
would require changing one of these behaviors, stop and report the risk unless
the prompt explicitly scopes it:

- scanner scoring, selection, thresholds, ranking, sorting, live/fallback labels;
- backtest calculations, fills, costs, metrics, benchmarks, stored results;
- portfolio accounting, cash, holdings, P&L, FX, cost basis, import/sync/replay;
- provider order, live-call paths, fallback behavior, circuit behavior,
  MarketCache TTL/SWR/cold-start/background refresh/cache keys;
- AI prompts, model routing, fallback, evidence weighting, recommendations;
- auth/RBAC/security, sessions, CSRF/CORS, password/token handling;
- notification routing and delivery;
- DuckDB/PostgreSQL source-of-truth behavior;
- Options Lab ranking, gates, payoff math, recommendation/no-trade policy;
- API response shapes and stored contract versions.

Source: [Backend Protected Domains](./codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md).

## Frontend Linear OS Maintenance

For frontend tasks, classify the route before editing:

- Home: `ResearchConsole`
- Scanner: `RankingBoard`
- Watchlist: `WatchBoard` / `DenseList`
- Market Overview, Liquidity, Rotation: `MarketMonitor`
- Portfolio: `RiskConsole` / `LedgerBoard`
- Options Lab: `ExperimentConsole`
- Admin/Ops: `OpsConsole`

Rules:

- shared shell owns root canvas, route width, and scroll rhythm;
- pages own route hierarchy and data orchestration;
- `components/linear` owns new user-facing material;
- `Terminal*` names are compatibility adapters only;
- keep one dominant workspace above the fold;
- prefer rows/tables/strips/rails/drawers/disclosures before cards;
- keep raw provider/schema/debug detail collapsed on user routes;
- verify desktop and narrow/mobile browser views for visible UI changes.

Do not claim a route is fully migrated unless current page code, tests, and
browser proof for that route support the claim. T-196 route migration status is
partial by default; exact route status must be checked on current main.

Source:

- [Linear OS Design Language](./codex/WOLFYSTOCK_LINEAR_OS_DESIGN_LANGUAGE.md)
- [Frontend Surface Usage](./codex/WOLFYSTOCK_FRONTEND_SURFACE_USAGE.md)
- [Frontend Route Templates](./codex/WOLFYSTOCK_FRONTEND_ROUTE_TEMPLATES.md)
- [Terminal Primitives Usage](./codex/WOLFYSTOCK_TERMINAL_PRIMITIVES_USAGE.md)
- [Visual Evidence Protocol](./codex/WOLFYSTOCK_CODEX_VISUAL_EVIDENCE_PROTOCOL.md)

## Backend, Provider, And Data Safety

Backend tasks should move through public facades, endpoint contracts, schemas,
DTOs, and services rather than reaching into another domain's internals.

Provider/data rules:

- preserve provider order, first-good-wins fallback, retry/circuit posture, and
  MarketCache semantics unless explicitly scoped;
- do not mark fallback/stale/mock/synthetic/fixture/repaired data as live;
- do not inspect, print, or document real secret values;
- keep provider capability metadata inert unless a task scopes runtime wiring;
- keep DuckDB disabled-by-default and diagnostic-only unless separately
  approved;
- keep PostgreSQL/SQLite coexistence posture honest and do not claim cutover
  without current proof.

Source:

- [Modular Architecture Manual](./architecture/WOLFYSTOCK_MODULE_ARCHITECTURE.md)
- [Backend Protected Domains](./codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md)
- [Provider Data Freshness Reliability Guide](./audits/provider-data-freshness-reliability-guide.md)
- [Provider Capability Metadata](./operations/provider-capability-metadata.md)
- [DuckDB Production Readiness Checklist](./operations/duckdb-production-readiness-checklist.md)

## Validation And Browser Proof Rules

Choose validation from the changed surface. Do not use green tests for one
surface as proof for another.

Docs-only:

```bash
git diff --check -- <changed-doc-files>
bash scripts/release_secret_scan.sh
git status --short --branch
git diff --name-only
git diff --cached --name-only
```

Frontend UI:

- focused route/component tests;
- lint/build/design guard as required by the task;
- browser proof on the requested route and viewports;
- no horizontal overflow;
- no console/page errors;
- no raw provider/schema/debug leakage on user routes;
- no stale screenshots or old preview bundles as evidence.

Backend:

- focused compile/tests for touched files;
- provider/cache/auth/backtest/portfolio/scanner tests when those semantics
  are near scope;
- full `./scripts/ci_gate.sh` only when required by task, release, or broad
  runtime impact.

Source:

- [Frontend Validation Playbook](./codex/WOLFYSTOCK_FRONTEND_VALIDATION_PLAYBOOK.md)
- [Visual Evidence Protocol](./codex/WOLFYSTOCK_CODEX_VISUAL_EVIDENCE_PROTOCOL.md)
- [CI Gate Usage](./audits/ci-gate-usage.md)

## Stale-Doc Traps

Common traps:

- Treating archived audit docs as current launch authority.
- Treating local `.claude/reviews/`, `.codex/`, screenshots, reports, or
  Playwright artifacts as current proof.
- Citing old route screenshots after a route migration.
- Assuming T-196 migration completed every route because one route landed.
- Treating provider capability metadata as runtime routing.
- Treating DuckDB diagnostics as production source-of-truth.
- Treating Options Lab fixture/dry-run output as live decision-grade data.
- Treating frontend display labels as backend semantic authority.
- Fixing stale docs by moving or deleting archives without explicit scope.

Current archive guidance:

- [Archive Index](./ARCHIVE_INDEX.md)
- [Audit Index](./audits/README.md)

## How To Use Existing Docs Before Changing Code

1. Start with [Docs Index](./DOCS_INDEX.md).
2. Read the [System Handbook](./WOLFYSTOCK_SYSTEM_HANDBOOK.md) for ownership.
3. Read the task-specific authority docs listed there.
4. Inspect current source files and tests for the exact route/module.
5. Check protected-domain docs if the task is near scanner, backtest,
   portfolio, provider, AI, auth, Options, MarketCache, API contracts, or
   storage truth.
6. Make the smallest scoped change.
7. Validate with task-focused commands.
8. Update docs/changelog only when the repo convention or task scope requires
   it.

## Documentation Maintenance Rules

- Link to current source docs instead of copying long sections.
- Prefer one current index over scattered navigation fragments.
- When changing docs navigation, update [Docs Index](./DOCS_INDEX.md) and
  consider [Changelog](./CHANGELOG.md).
- Do not edit `docs/codex/*` unless the task explicitly allows it.
- Do not move/delete/retire tracked docs unless the task explicitly scopes
  archive cleanup.
- If bilingual docs diverge, report why the untouched language was not updated.
- If `README.md` is not updated for a docs navigation change, report where the
  new entry lives and why README stayed unchanged.

## Handoff Checklist For AI Workers

Before final report:

- Confirm final diff is within the allowed file list.
- Confirm no staged unrelated files.
- Run required validation fresh.
- Read validation output and exit codes.
- Run `git diff --name-only` and `git diff --cached --name-only`.
- Commit with the exact requested English message if the task asks for commit.
- Push only the requested branch if the task asks for push.
- Report exact commit, push result, validation, risk, rollback, and final git
  status.
