# WolfyStock Codex Standard Guard

Purpose: baseline operating contract for Codex tasks in the WolfyStock repository. Task prompts should reference this file instead of repeating fixed rules. Task prompts may add stricter task-specific rules.

---

## 0. Default Execution Model

Default workflow:

- Use the Codex App isolated task workspace.
- Use local environment: `WolfyStock Fast`.
- Base from latest `origin/main`.
- Do not use or checkout long-lived manual worktree branches.
- Do not checkout `codex/frontend-lane` or `codex/backend-lane`.
- Do not create or use manual worktrees under `/Users/yehengli/worktrees` unless the user explicitly requests that mode.
- Report actual `cwd`, branch, and base commit in final reports.

Default dependency policy:

- Do not run `pip install`, `npm install`, `npm ci`, or `npm audit fix` unless dependency/lock files changed or the task explicitly requires dependency refresh.
- Reuse existing `.venv` and `node_modules` when provided by the environment.
- Never run `npm audit fix` as setup.

Use same-main shared worktree rules only when the user explicitly asks to work directly in `/Users/yehengli/daily_stock_analysis`. See `WOLFYSTOCK_SHARED_MAIN_WORKTREE_PROTOCOL.md`.

---

## 1. Preflight

Every task starts with:

```bash
pwd
git fetch origin
git status --short --branch
git log --oneline -5
git log --oneline --decorate origin/main..HEAD
git diff --name-only
git diff --cached --name-only
```

Stop and report if:

- staged files exist before the task starts;
- tracked dirty files exist before the task starts unless explicitly allowed;
- local branch is ahead of `origin/main` unexpectedly;
- target files are already dirty;
- the task would require checkout of forbidden long-lived branches;
- the task would require manual worktree creation;
- the task would require dependency installation outside scope.

Untracked `.codex/` may exist. Do not stage it unless the task explicitly changes Codex config.

---

## 2. Git Safety

Never use:

```bash
git add .
git reset
git clean
git checkout -- <unrelated-file>
git revert <unrelated-commit>
```

Rules:

- Stage only task-related files explicitly.
- Do not broad-format unrelated files.
- Do not restore, clean, reset, revert, stash, move, or overwrite unrelated work.
- If a changelog has unrelated hunks, stage only the task hunk or skip it and report why.
- Execution-class tasks should commit and push after validation unless blocked by tests, branch permissions, or explicit prompt scope.
- Read-only tasks must not stage, commit, or push.

---

## 3. Secrets and Sensitive Data

Do not print, inspect, copy, commit, or log real values for:

- passwords or password hashes;
- session IDs, cookies, tokens, API keys;
- `.env` values;
- provider or broker credentials;
- webhook URLs;
- private keys;
- raw prompts, raw provider payloads, or raw LLM responses containing private content;
- production DB contents;
- stack traces containing secrets or internal payloads.

Env var names may be mentioned. Env var values must not be printed.

Use sanitized reason codes, bounded labels, hashes, and redacted metadata.

---

## 4. Dev Server and Port Safety

Do not casually kill or restart shared servers.

Common shared ports:

- backend: `8000`, `8001`
- frontend/dev/preview: `5173`, `4173`, `4177`, `4178`, `4179`, `4180`, `5174`, `5175`, `5176`

If a frontend/dev server is needed:

- inspect ports first;
- prefer an isolated task-owned port;
- leave shared `5173` untouched unless the task owns it;
- stop only task-owned temporary servers;
- report inspected and used ports.

---

## 5. Protected Runtime Domains

Do not change protected domains unless explicitly scoped. For backend details, read `WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md`.

Protected domains include:

- scanner scoring, ranking, selection, thresholds, and sorting;
- backtest calculations, fills, costs, metrics, and stored result semantics;
- portfolio accounting, cash, holdings, P&L, sync, import, replay, FX, and cost basis;
- provider runtime order, live-call paths, fallback behavior, and freshness/live labeling;
- MarketCache TTL, SWR, cold-start fallback, background refresh, cache keys, and payload meaning;
- AI/LLM prompts, routing, model order, fallback, retry, thresholds, and recommendation semantics;
- auth/RBAC/security behavior;
- notification routing and delivery semantics;
- DuckDB/PostgreSQL source-of-truth behavior;
- Options Lab ranking/gates/recommendation policy;
- API response shapes and stored contract versions.

Task prompts should list only task-specific protected domains when near a protected area.

---

## 6. Engineering Cleanliness and Reuse

Before adding helpers, components, services, docs, wrappers, or namespaces:

- search for existing utilities, services, types, components, tests, and docs;
- prefer deletion, consolidation, or direct reuse over adding a layer;
- avoid duplicating status, label, freshness, provider, evidence, or design mappings;
- avoid page-local UI controls/material when shared primitives exist;
- justify any new abstraction in the final report.

Wrapper rule:

- New wrappers are forbidden unless they create a real boundary, have focused tests, and include a future deletion/migration path.
- Compatibility layers are temporary; document owner, scope, and exit path.

---

## 7. Frontend Design Rules

Frontend implementation tasks must also read:

- `CODEX_FRONTEND_DESIGN_CONSTITUTION.md`
- `WOLFYSTOCK_LINEAR_OS_DESIGN_LANGUAGE.md`
- `WOLFYSTOCK_FRONTEND_SURFACE_USAGE.md`
- `WOLFYSTOCK_FRONTEND_ROUTE_TEMPLATES.md`
- `WOLFYSTOCK_TERMINAL_PRIMITIVES_USAGE.md`
- `WOLFYSTOCK_FRONTEND_VALIDATION_PLAYBOOK.md`

Current visual direction:

```text
WolfyStock Linear OS
charcoal canvas, slim product shell, quiet command bar
one dominant console or board surface per route
rows, tables, strips, rails, and drawers before cards
Terminal* names are compatibility only, rendered with Linear OS material
```

Rules:

- no terminal cosplay, OLED glow, ghost-glass, or bento/card-first regressions;
- no pure-black root gutters, stretched slabs, or admin/Web1 chrome in user-facing routes;
- new user-facing surfaces should prefer `apps/dsa-web/src/components/linear` primitives;
- no Web3/dApp visual language unless task-scoped;
- no raw provider/schema/debug leakage in default user UI;
- no meta-explanatory UI copy such as `可信度较高`, `决策依据可查看`, `结果已整理`, `摘要可读`;
- Chinese UI labels by default;
- desktop and mobile layouts must both be usable;
- no horizontal overflow;
- primary task must be visible above fold;
- critical warnings remain honest but compact.

---

## 8. Financial/Product Safety

Do not add buy/sell/order CTAs unless explicitly requested and safety-reviewed.

Forbidden wording for trading/Options surfaces:

```text
买入按钮
下单
立即交易
必买
稳赚
保证收益
guaranteed
best contract
AI recommends you buy
```

Use analytical labels such as:

```text
数据不足，禁止判断
不建议
仅观察
有条件可交易
高风险，仅小仓验证
```

Do not present outputs as personalized financial advice. Preserve disclaimers and risk boundaries.

---

## 9. Validation

Run focused validation first. Escalate only when the task touches shared/high-risk runtime or the prompt requires it.

Common frontend validation:

```bash
npm --prefix apps/dsa-web run test -- <focused tests> --run
npm --prefix apps/dsa-web run build
npm --prefix apps/dsa-web run check:design
python3 scripts/check_frontend_design_constitution.py
git diff --check
bash scripts/release_secret_scan.sh
```

Common backend validation:

```bash
python3 -m py_compile <changed python files>
python3 -m pytest <focused tests> -q
git diff --check
bash scripts/release_secret_scan.sh
```

Full `./scripts/ci_gate.sh` is for landing/release/high-risk backend changes, not default docs-only or narrow frontend tasks.

---

## 10. Final Report Requirements

Use `WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md`.

Final reports must include:

- task ID and title;
- actual cwd/branch/base commit;
- files changed;
- what changed;
- protected domains touched or explicitly untouched;
- validation commands and results;
- browser verification for frontend UI;
- commit hash and push status;
- rollback command;
- final git status.
