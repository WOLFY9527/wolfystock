# WolfyStock Codex Task Runtime Rules

Suggested project path:

```text
docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md
```

Purpose: keep Codex prompts compact without losing operational constraints. Every Codex task prompt may reference this file instead of repeating the same SOP.

---

## 1. Core operating rules

1. Treat every task as bounded by its prompt, this file, and the referenced project guard/design docs.
2. Do not expand scope. If the prompt says audit, do not edit. If the prompt says shell/layout only, do not change behavior.
3. Prefer small, reviewable changes over broad refactors.
4. Stage only task-related files.
5. Never use `git add .`.
6. Push only the task branch named in the prompt.
7. Do not commit unrelated formatting, lockfile, config, generated, or cache changes.
8. If the workspace, branch, or git root does not match the prompt, stop and report the mismatch.
9. If a protected domain appears necessary, stop and report the risk instead of modifying it.
10. If validation cannot run, report exactly why, with the command attempted and the blocking output.

---

## 2. Model / reasoning selection

The caller selects model and reasoning in the Codex UI or surrounding task title. The prompt body should not need model/reasoning lines.

Default policy:

```text
Execution tasks: 5.4 + high
Decision / architecture / high-risk audit tasks: 5.5 + xhigh
```

Task prompts should remain model-agnostic and focus only on task scope.

---

## 3. Required prompt fields

Each task prompt should still include these task-specific fields:

```text
Task title:
Branch:
Workspace:
Mode:
Read:
Goal:
Allowed files:
Forbidden files:
Implementation:
Protected semantics:
Validation:
Browser:
Final report:
```

The prompt may omit sections only when clearly not applicable, such as Browser for backend-only tasks.

---

## 4. Execution modes

### SERIAL-MAIN

Use when the task is a single safe task on `main` and there is no true parallelism need.

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
- Stop if the branch/path mismatch
- Push only this branch
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

---

## 5. Parallelization rules

Parallelize only when workers do not write overlapping files or semantically coupled domains.

Safe parallelism examples:

```text
- One UI shell page + one backend read-only audit
- Two UI pages if they do not share files/components
- Scanner read-only audit + Options endpoint audit
```

Unsafe parallelism examples:

```text
- Multiple workers editing UserScannerPage.tsx
- Multiple workers editing the same Admin provider page family
- Multiple workers editing OptionsLabService and the Options endpoint at the same time
- Multiple workers editing PortfolioPage
- Any worker touching shared primitives/global CSS while another UI worker runs
```

If not clearly safe, serialize.

---

## 6. Protected domains

Unless the prompt explicitly scopes the domain and names the allowed files, do not modify these.

### Scanner

Do not change:

```text
- scoring
- ranking
- sorting
- selection
- result order
- scanner-to-backtest payload
- watchlist behavior
- export behavior
- copy behavior
- API fetch/run/theme/simulation semantics
```

Allowed in small frontend extraction tasks only when scoped:

```text
- presentational components
- Suspense fallback
- static display helpers
- diagnostics view rendering
```

### Portfolio

Do not change:

```text
- accounting
- cash
- holdings
- P&L
- FX
- cost basis
- broker sync
- import logic
- manual ledger logic
- API behavior
```

UI shell work may change layout/background/grid only.

### Provider runtime / MarketCache

Do not change:

```text
- provider order
- live-call semantics
- fallback semantics
- MarketCache TTL
- SWR behavior
- cold-start behavior
- provider runtime files
```

Provider runtime changes require a dedicated audit first.

### Options

Do not change:

```text
- ranking
- gates
- scoring
- payoff math
- optimizer behavior
- no-trade policy
- provider/runtime behavior
- public API response shape
- aliases
```

Endpoint mapping work must preserve public contracts.

Do not remove or reshape these unless explicitly scoped after audit:

```text
- OptionContract
- OptionGreeks
```

### Backtest

Backtest credibility lane is closure-ready. Do not expand features unless explicitly requested.

Do not change:

```text
- primary calculations
- fills
- costs
- metrics
- rule_backtest_engine.py
- stored readback authority
```

Do not add by default:

```text
- true parameter sweep job
- portfolio/multi-asset rebalance
- expanded robustness knobs
- expanded regime attribution
```

### Auth / RBAC / Security

Do not change:

```text
- auth flow
- RBAC gates
- permission checks
- secret redaction
- security middleware
```

### Frontend design system

Do not change unless explicitly scoped:

```text
- Terminal primitive implementation
- global CSS
- index.css
- app-wide layout primitives
```

Avoid:

```text
- native gray blocks
- page-local pure-black slabs
- raw debug copy
- raw schema/provider/internal terms
- unexplained noisy helper text
```

---

## 7. WolfyStock frontend shell rules

WolfyStock visual direction:

```text
Deep Space / Ghost UI
shared terminal background
high-density professional trading terminal
cards float on the shared page background
no page-local pure-black inner slab
no native gray container look
no raw provider/schema/debug leakage
```

For shell/background alignment tasks:

Do:

```text
- let shared app shell / TerminalPageShell own the page background
- keep TerminalGrid as the 12-column layout owner
- preserve TerminalPanel / terminal card language
- ensure full-width rows use col-span-12 and min-w-0 where needed
- keep existing test ids, filters, controls, and permission gates
```

Do not:

```text
- rewrite Terminal primitives
- rewrite global CSS
- change API behavior
- change data fetching behavior
- change auth/RBAC behavior
- introduce new feature copy
- add large saturated blocks
- add native gray wrappers
```

Common drift patterns to remove when task-scoped:

```text
bg-black
bg-[#030303]
bg-[#050505]
bg-neutral-*
min-h-screen route roots
page-local fixed backgrounds
duplicated route-level padding around TerminalPageShell
```

---

## 8. Backend boundary rules

Backend refactors must preserve public API behavior unless the prompt explicitly states a contract change.

For endpoint mapping tasks:

```text
- service layer should return internal models or domain data
- endpoint layer owns API response schemas
- public response shape and aliases must remain stable
- add/adjust focused contract tests where possible
```

For tests-only guards:

```text
- do not alter runtime code
- freeze the current boundary/import inventory
- make failure messages actionable
```

---

## 9. Validation commands

Run focused validation first. Run broader validation when the task touches shared frontend/backend infrastructure or when the prompt requires it.

### Worker vs landing validation matrix

`scripts/ci_gate_fast.sh` is worker-iteration evidence only. It is useful for quick local feedback, but it does not replace task-scoped checks or landing proof.

`./scripts/ci_gate.sh` is for landing, release, or high-risk code-bearing backend changes. Do not treat it as the default gate for docs-only, tests-only, or narrow frontend worker tasks.

| Task class | Worker default | Landing / pre-push escalation |
| --- | --- | --- |
| frontend shell | focused page/component tests; `npm --prefix apps/dsa-web run build`; `npm --prefix apps/dsa-web run check:design`; focused Playwright on touched route(s); `git diff --check`; optional `./scripts/ci_gate_fast.sh` for iteration | run `bash scripts/release_secret_scan.sh` before commit/push; add `tsc --noEmit` only if routes/types/shared interfaces changed or build is not enough; use full `./scripts/ci_gate.sh` only if the slice also touched shared/high-risk runtime or landing policy explicitly requires it |
| backend tests-only guard | focused `pytest` on touched tests/fixtures/guards; `git diff --check`; optional `./scripts/ci_gate_fast.sh` for quick iteration | run `bash scripts/release_secret_scan.sh` before commit/push; do not jump to full `./scripts/ci_gate.sh` unless the task stopped being tests-only or landing policy requires it |
| backend endpoint mapping | `python3 -m py_compile <changed python files>`; focused `pytest -q` contract/boundary coverage; `git diff --check`; optional `./scripts/ci_gate_fast.sh` while iterating | run `bash scripts/release_secret_scan.sh` before commit/push; run full `./scripts/ci_gate.sh` before claiming the backend change is ready to land |
| provider/runtime audit | read-only commands only; inspect current code/tests/docs; no secret scan for pure read-only audit; no `ci_gate_fast.sh` / `ci_gate.sh` by default | if the audit becomes a write task, re-scope it first; provider/runtime landing work is high-risk and should use `bash scripts/release_secret_scan.sh` plus full `./scripts/ci_gate.sh` |
| scanner/backtest protected domains | stay route- or file-scoped; run only the focused tests/browser checks needed for the touched seam; avoid unrelated broad suites; use focused Playwright when a worker changed UI on a touched route | run `bash scripts/release_secret_scan.sh` before commit/push; use full `./scripts/ci_gate.sh` when landing code-bearing scanner/backtest changes or when protected-domain risk widened beyond a narrow seam |
| docs-only | verify command/file-name consistency; `git diff --check` | for docs write tasks, run `bash scripts/release_secret_scan.sh` before commit/push or landing; for read-only audits, skip secret scan and do not run `ci_gate_fast.sh` / `ci_gate.sh` |

### Frontend validation

```bash
npm --prefix apps/dsa-web run lint
npm --prefix apps/dsa-web run test -- <focused-test> --run
npx --prefix apps/dsa-web tsc --noEmit --pretty false --project apps/dsa-web/tsconfig.app.json
npm --prefix apps/dsa-web run build
npm --prefix apps/dsa-web run check:design
/Users/yehengli/daily_stock_analysis/.venv/bin/python scripts/check_frontend_design_constitution.py
git diff --check
bash scripts/release_secret_scan.sh
```

Notes:

```text
- Route-focused Playwright is the worker default for frontend browser proof.
- Avoid duplicate `tsc --noEmit` + build unless the task changed routes, shared types/interfaces, or build output is not enough to prove safety.
- Use `bash scripts/release_secret_scan.sh` before commit/push or landing for write tasks, not for pure read-only audits.
```

### Backend validation

```bash
/Users/yehengli/daily_stock_analysis/.venv/bin/python -B -m py_compile <files>
/Users/yehengli/daily_stock_analysis/.venv/bin/python -B -m pytest -q <focused-tests>
git diff --check
bash scripts/release_secret_scan.sh
```

### Read-only audit validation

Allowed:

```bash
git status --short --branch
rg <pattern>
npm --prefix apps/dsa-web run check:design
pytest --collect-only <focused-path>
```

Do not run destructive commands in read-only audits.

---

## 10. Browser verification

Frontend route/UI tasks require browser verification unless impossible.

Use isolated preview port where possible.

Required viewports:

```text
1440x1000
390x844
```

Check:

```text
- no horizontal overflow
- no console/page errors
- no pure-black inner page slab
- mobile stacks cleanly
- route sections remain visible
- no raw/debug/provider/schema leakage
- no behavior regression in the scoped feature
```

If real credentials are unavailable, auth/API mocks are acceptable only when reported clearly in the final report.

---

## 11. Git and commit rules

Before work:

```bash
git status --short --branch
git fetch origin
```

For write tasks:

```text
- keep diff focused
- stage only task-related files
- never use git add .
- commit with a scoped conventional message
- push only the named task branch
```

Recommended commit styles:

```text
refactor(ui): align <page> shell background
refactor(scanner): extract <presenter>
refactor(options): move <mapping> to endpoint
test(provider): guard <boundary>
fix(portfolio): harden <layout contract>
```

Do not delete remote branches or remove worktrees unless the prompt explicitly asks for integration cleanup.

---

## 12. Final report format

Every worker final report must include:

```text
Summary:
- What changed or what was found

Files changed:
- path + purpose

Protected semantics:
- Explicitly state protected domains were not changed

Validation:
- command: PASS/FAIL/SKIPPED
- include blocker reason for skipped/failed commands

Browser:
- route(s)
- viewport(s)
- result
- auth/mock notes if any

Commit:
- branch
- commit hash
- push status

Risks / follow-ups:
- remaining risks
- recommended next slice if applicable
```

For read-only audits, replace Files changed with Files inspected and Commit with `No commit; read-only`.

---

## 13. Compact prompt template: execution

Use this shape for small write tasks.

```text
Task title:
...

Branch:
...

Workspace:
...

Mode:
WORKTREE-WORKER / SERIAL-MAIN

Read:
- docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md
- docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md
- docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md
- task-relevant docs

Goal:
...

Allowed files:
...

Forbidden files:
...

Implementation:
...

Protected semantics:
...

Validation:
...

Browser:
...

Final report:
Use the project final report template and include commit hash, validation, browser notes, and risks.
```

---

## 14. Compact prompt template: read-only audit

```text
Task title:
...

Branch:
main

Workspace:
/Users/yehengli/daily_stock_analysis

Mode:
READ-ONLY-AUDIT

Read:
- docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md
- docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md
- task-relevant docs

Rules:
Read-only. Do not edit files. Do not create artifacts. Do not commit or push.

Goal:
...

Allowed files to inspect:
...

Forbidden files:
No edits anywhere. Do not modify runtime behavior.

Audit method:
...

Validation:
Read-only commands only.

Final report:
Include summary, files inspected, findings, recommended next slices, risks, and no-commit confirmation.
```

---

## 15. Current strategic defaults

Unless a newer task prompt overrides these:

```text
- Primary focus: unified frontend shell/background/grid cleanup
- Admin/control-plane black inner slab drift should be closed in small route slices
- Scanner work should remain small presenter extraction
- Options work should remain endpoint mapping / boundary cleanup
- Backtest feature expansion is paused
- Provider runtime refactor is paused; audits and tests-only guards are preferred
```

---

## 16. Stop conditions

Stop and report instead of improvising if:

```text
- git root / branch / workspace mismatch
- untracked or unrelated changes would be overwritten
- task requires protected domain changes not explicitly allowed
- tests reveal behavior regression outside scope
- browser check reveals layout break outside the scoped page
- public API shape would change
- provider/runtime fallback semantics would change
- auth/RBAC/security behavior would change
```
