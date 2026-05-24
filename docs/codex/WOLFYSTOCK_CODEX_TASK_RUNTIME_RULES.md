# WolfyStock Codex Task Runtime Rules

Purpose: keep Codex prompts compact without losing operational constraints. Every Codex task prompt may reference this file instead of repeating the same SOP.

## 1. Core Operating Rules

1. Treat every task as bounded by its prompt, this file, and the referenced project guard/design docs.
2. Do not expand scope. If the prompt says audit, do not edit. If the prompt says shell/layout only, do not change behavior.
3. Prefer small, reviewable changes over broad refactors.
4. Stage only task-related files.
5. Never use `git add .`.
6. Push only when the prompt's `Commit` section authorizes it, and only to the prompt-named target branch.
7. Do not commit unrelated formatting, lockfile, config, generated, or cache changes.
8. If the workspace, branch, or git root does not match the prompt, stop and report the mismatch.
9. If a protected domain appears necessary, stop and report the risk instead of modifying it.
10. If validation cannot run, report exactly why, with the command attempted and the blocking output.

## 2. Model / Reasoning Selection

The caller selects model and reasoning in the Codex UI or surrounding task title. The prompt body should not need model/reasoning lines.

Default policy:

```text
Low-risk docs/tests/small fixes: 5.4 + medium
Normal bounded execution: 5.4 + high
Architecture / high-risk / protected-domain audits / multi-report integration: 5.5 + xhigh
```

Use the lowest route that fits the task risk. Do not repeat model/reasoning lines in every prompt unless overriding the default route.

## 3. Required Prompt Fields And Efficiency

Each task prompt should include these task-specific fields:

```text
Task ID:
Task title:
Branch:
Workspace:
Mode:
Read and obey:
Current context:
Goal:
Allowed final diff:
Forbidden final diff:
Implementation:
Protected semantics:
Validation:
Browser:
Commit:
Final report:
```

Task ID should be stable and must match the final report.

Prompt efficiency rules:

- Keep the `Read and obey:` prefix stable so shared docs stay cache-friendly.
- Include only necessary shared docs; do not paste rules already covered here or in the standard guard.
- Keep `Current context` to 3-5 lines of task-specific state and recent decisions.
- Use exact `Allowed final diff` paths or path globs; avoid broad `docs/**` unless truly scoped.
- Merge validation commands into the smallest faithful command group when order does not matter.
- Use standard `Mode` names only: `CODEX-ISOLATED`, `SERIAL-MAIN`, `WORKTREE-WORKER`, `READ-ONLY-AUDIT`.

## 4. Task Ledger Statuses

Use one exact status:

```text
RUNNING       active worker task
READY TO LAND validated/committed/pushed task awaiting review or merge
LANDED        merged or otherwise landed into target branch
NO-OP         no code/doc change required
BLOCKED       cannot continue because of a concrete blocker
PLANNED       scoped only; implementation has not started
```

## 5. Execution Modes

The only standard `Mode` values are `CODEX-ISOLATED`, `SERIAL-MAIN`, `WORKTREE-WORKER`, and `READ-ONLY-AUDIT`. Do not invent aliases or mixed names.

### CODEX-ISOLATED

Use as the default execution mode for normal Codex App tasks.

Rules:

```text
- Use the Codex App isolated task workspace.
- Use local environment: WolfyStock Fast.
- Base from latest origin/main.
- Do not create or use manual worktrees.
- Do not work directly in /Users/yehengli/daily_stock_analysis unless the prompt explicitly switches to SERIAL-MAIN.
- Report actual cwd, branch, and base commit.
- Push only if the prompt's Commit section authorizes it.
```

### SERIAL-MAIN

Use only when the user explicitly asks to work directly in the shared `/Users/yehengli/daily_stock_analysis` main worktree.

Rules:

```text
- Work only in /Users/yehengli/daily_stock_analysis
- Stay on main unless prompt says otherwise
- Do not create a worktree
```

### WORKTREE-WORKER

Use only for true parallel work.

Rules:

```text
- Work only in the workspace path given by the prompt
- Branch must match the branch given by the prompt
- Stop if branch/path mismatch
- Push only this branch, and only if the prompt's Commit section authorizes it
```

### READ-ONLY-AUDIT

Use for audits, design checks, inventories, and risk mapping.

Rules:

```text
- Do not edit files
- Do not create artifacts
- Do not commit
- Do not push
- Do not run destructive commands
```

Audit discipline:

- Avoid mechanical `READ-ONLY-AUDIT -> execution -> post-merge audit` chains for low-risk docs, tests, copy, and small fixes.
- Use audits mainly for high-risk, protected-domain, unclear, or cross-surface work where separate evidence changes the decision.
- For low-risk bounded tasks, prefer one execution prompt with focused preflight, implementation, validation, and concise final report.

## 6. Parallelization Rules

Parallelize only when workers do not write overlapping files or semantically coupled domains.

Safe examples:

```text
- one UI page migration + one backend read-only audit
- two UI pages if they do not share files/components
- scanner read-only audit + options endpoint audit
```

Unsafe examples:

```text
- multiple workers editing the same page
- multiple workers editing the same service/endpoint family
- any worker touching shared primitives/global CSS while another UI worker runs
- portfolio or options behavior work split across multiple writers
```

If not clearly safe, serialize.

## 7. Protected Domains

Unless the prompt explicitly scopes the domain and names allowed files, do not modify:

- scanner scoring/ranking/sorting/selection/result order;
- portfolio accounting/cash/holdings/P&L/FX/cost basis/broker sync/import/manual ledger/API behavior;
- provider order, live-call semantics, fallback semantics, MarketCache TTL/SWR/cold-start behavior;
- options ranking/gates/scoring/payoff math/optimizer/no-trade policy/API response shape;
- backtest primary calculations/fills/costs/metrics/stored readback authority;
- auth/RBAC/security;
- API response contracts and stored contract versions.

Frontend shell work may change layout/background/grid only when explicitly scoped.

## 8. WolfyStock Frontend Shell Rules

WolfyStock visual direction:

```text
WolfyStock Linear OS
charcoal shared app canvas
slim product-first shell
one dominant console/board/workbench surface
rows/tables/strips/rails before cards
no page-local pure-black island
no generic admin layout for product routes
no raw provider/schema/debug leakage
```

For shell/background alignment tasks:

Do:

```text
- let the shared app shell own the root canvas
- classify the route surface before editing
- prefer components/linear for new user-facing work
- keep Terminal* names as compatibility adapters when existing pages use them
- ensure full-width rows use col-span-12 and min-w-0 where needed
- keep existing test IDs, filters, controls, and permission gates
```

Do not:

```text
- rewrite unrelated pages
- rewrite global CSS beyond the scoped token/shell change
- change API behavior
- change data fetching behavior
- change auth/RBAC behavior
- introduce new feature copy
- add large saturated blocks
- add native gray wrappers
- preserve card-first/bento-first structures under new colors
```

## 9. Validation Commands

Run focused validation first. Run broader validation when the task touches shared frontend/backend infrastructure or when the prompt requires it.

### Frontend validation

```bash
npm --prefix apps/dsa-web run lint
npm --prefix apps/dsa-web run test -- <focused-test> --run
npx --prefix apps/dsa-web tsc --noEmit --pretty false --project apps/dsa-web/tsconfig.app.json
npm --prefix apps/dsa-web run build
npm --prefix apps/dsa-web run check:design
python3 scripts/check_frontend_design_constitution.py
git diff --check
bash scripts/release_secret_scan.sh
```

Run TypeScript separately only when shared interfaces/routes/types changed or build is insufficient.

### Docs-only

```bash
git diff --check -- <changed-doc-files>
git status --short --branch
bash scripts/release_secret_scan.sh
```

Merged form for compact prompts:

```bash
git diff --check -- <changed-doc-files> && ./scripts/release_secret_scan.sh && git status --short --branch
```

### Backend endpoint mapping

```bash
python3 -m py_compile <changed python files>
python3 -m pytest -q <focused tests>
git diff --check
bash scripts/release_secret_scan.sh
```

Use full `./scripts/ci_gate.sh` for release/landing or high-risk backend runtime changes, not as a default for every narrow task.
