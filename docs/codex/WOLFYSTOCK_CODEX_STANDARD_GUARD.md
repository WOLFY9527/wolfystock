# WolfyStock Codex Standard Guard

Use this file as the baseline operating contract for Codex tasks in the WolfyStock repository. Task prompts should reference this file instead of repeating every fixed rule. Task-specific prompts may add stricter rules when needed.

## 1. Repository and branch preflight

Default repository:

```bash
cd /Users/yehengli/daily_stock_analysis
```

Default branch:

```bash
main
```

Every task must start with:

```bash
cd /Users/yehengli/daily_stock_analysis
pwd
git branch --show-current
git status --short
git status --branch --short
git log --oneline -40
./scripts/task_preflight.sh || true
```

Then inspect common shared dev ports without killing anything:

```bash
lsof -i :8000 -i :8001 -i :5173 -i :4173 -i :5174 -i :5175 -i :5176 -i :4177 || true
```

Stop immediately and report if:

- `pwd` is not `/Users/yehengli/daily_stock_analysis`;
- branch is not `main` unless the user explicitly requested another branch;
- task target files are already dirty before your changes;
- another concurrent task is clearly modifying the same target domain.

## 2. Git safety

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
- Do not restore, clean, reset, revert, or overwrite unrelated work.
- If a target file is dirty before your work, stop and report conflict risk.
- If a file becomes dirty from another task while you are working, do not stage it unless it is explicitly part of your task and you can prove the diff belongs to you.
- If a changelog file has unrelated hunks, stage only your hunk or leave changelog unstaged and report why.

## 3. Secrets, credentials, and sensitive data

Do not print, inspect, copy, commit, or log real values for:

- passwords or password hashes;
- session IDs, cookies, tokens, API keys;
- `.env` values;
- provider credentials;
- broker credentials;
- webhook URLs;
- private keys;
- raw prompts;
- raw provider payloads;
- raw LLM responses if they may contain user/private content;
- raw stack traces that contain secrets or internal payloads;
- production DB contents.

Env var names may be mentioned. Env var values must not be printed.

Use sanitized reason codes, bounded labels, hashes, and redacted metadata where needed.

## 4. Dev server and port safety

Do not casually kill or restart shared servers.

Common shared ports:

- backend: `8000`, `8001`
- frontend/dev/preview: `5173`, `4173`, `5174`, `5175`, `5176`, `4177`

If a frontend/dev server is needed:

- prefer an isolated port;
- do not reuse or kill shared ports unless the task explicitly requires it and ownership is clear;
- report all ports inspected and used;
- stop only task-owned temporary servers.

## 5. Protected runtime domains

Do not change these domains unless the task explicitly asks for it:

- scanner scoring, ranking, selection, or thresholds;
- backtest calculations;
- portfolio accounting, cash, holdings, P&L, sync, import, replay, FX;
- broker execution or order placement;
- market provider ordering/fallback behavior;
- MarketCache TTL, SWR, cold-start fallback, background refresh, or payload shape;
- AI/LLM prompts, routing, model order, fallback, retry, or integrity retry;
- notification routing or delivery semantics;
- DuckDB production runtime;
- auth/RBAC/security behavior;
- quota enforcement;
- cost ledger storage/reconciliation;
- Options Lab / Options Decision Engine;
- provider circuit enforcement.

Task prompts should list task-specific protected domains only when the task is near one of them. Otherwise, reference this file.

## 6. Audit and reuse expectations

Before adding new helpers, components, or patterns:

- search for existing utilities, services, types, components, tests, and docs;
- reuse established helpers when appropriate;
- avoid duplicating status/label/freshness/provider mappings;
- avoid ad-hoc UI controls when shared controls exist;
- justify any new abstraction in the final report.

For frontend/UI tasks, read:

```text
CODEX_FRONTEND_DESIGN_CONSTITUTION.md
```

For architecture-sensitive tasks, read the relevant audit/design docs before coding.

## 7. Frontend design rules

For WolfyStock frontend work:

- preserve OLED/deep-space/ghost-glass visual language;
- no solid gray backgrounds;
- no native-looking controls;
- no default scrollbars;
- Chinese UI labels by default;
- no noisy explainer copy;
- no huge dead layout bands;
- raw/debug/provider/schema/developer details collapsed by default;
- desktop and mobile/narrow layouts must both be usable;
- no horizontal overflow;
- prefer Playwright verification when practical.

Use established components and styling patterns.

## 8. Financial/product safety

Do not add buy/sell/order CTAs unless explicitly requested and safety-reviewed.

Forbidden wording for trading/Options surfaces:

- `买入按钮`
- `下单`
- `立即交易`
- `必买`
- `稳赚`
- `保证收益`
- `guaranteed`
- `best contract`
- `AI recommends you buy`

Use analytical labels such as:

- `数据不足，禁止判断`
- `不建议`
- `仅观察`
- `有条件可交易`
- `高风险，仅小仓验证`

Do not present outputs as personalized financial advice. Always preserve no-advice disclosure where relevant.

## 9. Validation policy

Always run task-focused validation.

### Docs-only tasks

Run:

```bash
git diff --check -- <changed-doc-files>
git status --short
```

No full `ci_gate` is required for docs-only tasks.

### Frontend tasks

Run targeted checks such as:

```bash
cd apps/dsa-web
npm test -- --run <relevant-tests>
npm run lint --if-present
npm run build --if-present
npm run check:design --if-present
```

Use Playwright/browser verification when relevant:

- desktop viewport, usually `1440x1000`;
- mobile/narrow viewport, usually `390x844`;
- confirm no console/page errors;
- confirm no horizontal overflow;
- confirm capability-gated hidden panels do not fetch protected APIs.

### Backend/service tasks

Run:

```bash
python3 -m py_compile <changed-python-files>
pytest <focused-tests> -q
```

Also run relevant regression tests for the touched domain.

### High-risk backend tasks

Tasks touching any of these are high risk:

- `src/storage.py`;
- schema/init/migration files;
- auth/session/RBAC/security;
- core analysis/pipeline/task queue;
- provider/cache/MarketCache;
- quota/cost runtime;
- broker/order paths;
- portfolio/accounting.

For high-risk tasks, run `./scripts/ci_gate.sh` only when the worktree is clean enough and practical.

If unrelated dirty files exist, skip/defer `ci_gate` unless the task itself is high risk and the result will still be meaningful. Report:

```text
ci_gate deferred due to unrelated dirty worktree
```

Before final push/merge, run one clean full gate:

```bash
./scripts/ci_gate.sh
```

## 10. Browser verification policy

When browser verification is relevant:

- prefer Playwright first;
- use an isolated frontend port;
- mock auth/status and API routes where needed;
- verify desktop and mobile/narrow viewports;
- report exact viewport sizes;
- report console errors and page errors;
- report horizontal overflow status;
- report whether real backend, mocked backend, or hybrid verification was used.

If browser verification is blocked, report the exact blocker honestly.

## 11. Task-specific prompt structure

Use shorter task prompts. Prefer this structure:

```text
Task: <short task name>

Repo:
cd /Users/yehengli/daily_stock_analysis
Branch: main

Read first:
- docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md
- <task-specific docs/files>

Goal:
<clear 3-6 line goal>

Scope:
Change:
- <allowed domains/files>

Do not change:
- <only task-specific protected domains>

Implementation:
1. ...
2. ...
3. ...

Tests:
- <focused tests>
- <frontend/browser checks if relevant>
- Follow validation policy in WOLFYSTOCK_CODEX_STANDARD_GUARD.md.

Commit:
- Stage only task-related files.
- Commit message: <message>

Final report:
Use the standard final report format, plus:
- <task-specific required fields>
```

## 12. Standard final report format

Every Codex final report should include:

- commit hash and commit message, or state no commit was created;
- changed files;
- behavior changed;
- behavior explicitly not changed;
- tests/checks run and exact results;
- `ci_gate` result, or why it was deferred/skipped;
- browser/Playwright verification details if relevant;
- ports inspected/used;
- final `git status` summary;
- rollback command if a commit was created;
- confirmation no real secrets were printed or committed;
- confirmation unrelated files were not touched/staged/committed.

High-risk tasks should also include:

- schema/helper/table changes;
- owner/capability/security boundary decisions;
- data-sanitization behavior;
- compatibility notes;
- known remaining blockers.

## 13. Commit message style

Use clear conventional messages, for example:

- `feat(options): add trade quality decision engine`
- `fix(options): prevent options lab black screen`
- `feat(cost): propagate owner context to llm ledger`
- `docs(ws2): design multi-instance smoke tests`
- `test(admin): add admin auth browser harness`

Do not combine unrelated tasks into one commit.

## 14. Rollback guidance

For normal single commits, report:

```bash
git revert <commit>
```

If no commit was created, state that rollback is not needed.

If rollback may conflict because of concurrent work, say so.

## 15. When to stop and report

Stop immediately and report if:

- wrong repo or branch;
- target files already dirty;
- required dependency/tool is unavailable and no safe fallback exists;
- task would require live credentials or paid provider calls not explicitly approved;
- task would require changing protected domains outside scope;
- tests reveal a serious unrelated failure that would require editing unrelated files;
- you cannot complete without risking secrets or unrelated work.

Partial completion is acceptable only if clearly reported and not staged/committed incorrectly.
