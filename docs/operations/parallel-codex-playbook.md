# Parallel Codex Operator Playbook

## 1. Purpose

WolfyStock often runs multiple Codex sessions in the same repository on `main` to avoid repeated dependency setup and duplicated local service bootstrapping. Same-repo parallel work is acceptable when each session has a clear task boundary and stages only its own files.

The main risk is not dirty files by themselves. The main risk is accidentally overwriting, formatting, staging, committing, or pushing unrelated work from another active session.

## 2. Default workflow

Start every task with the current repository reality:

```bash
cd /Users/yehengli/daily_stock_analysis
pwd
git branch --show-current
git status --short
git status --branch --short
git log --oneline -12
```

If the preflight helper exists and the task scope allows script inspection, run:

```bash
./scripts/task_preflight.sh
```

Dirty files are expected during parallel work. Categorize them by area and ownership instead of cleaning them automatically.

## 3. Same-repo parallel safety rules

- Work directly on `main` unless the task explicitly says to create or use a branch/worktree.
- Do not create a worktree by default.
- Do not stage, touch, revert, or format unrelated files.
- Do not run broad formatting across the repository.
- Before editing, inspect whether the files you need are already dirty.
- If a required file is already dirty from another session, either create a standalone doc/adjacent file or stop and report the conflict.
- Stop and report if the same file appears actively modified by another session and cannot be safely avoided.
- Run `git diff --stat` and `git status --short` before staging.
- Stage explicit paths only. Avoid `git add .`.

## 4. Task boundary checklist

Before editing, answer:

- What files will this task likely touch?
- Are any of those files already dirty?
- Are active tasks touching the same product area?
- What files must not be touched?
- What tests are targeted for this task?
- Does the task require browser verification?
- Does it require backend, frontend, or both servers?
- Which dev-server port will be used?
- What generated artifacts must be ignored?

## 5. Dev-server port safety

- Do not kill or restart shared backend/frontend servers unless the task explicitly requires it or the operator approves it.
- Inspect common ports before starting anything:

```bash
lsof -i :8000
lsof -i :8001
lsof -i :5173
lsof -i :4173
lsof -i :5174
lsof -i :5175
lsof -i :5176
```

- Use `8000` or `8001` for backend checks only after confirming ownership.
- Use `5173`, `4173`, `5174`, `5175`, or `5176` for frontend/dev/preview only after confirming ownership.
- A frontend-only task should prefer a separate frontend port and reuse an existing backend when possible.
- A backend+frontend task may use separate backend and frontend ports.
- Always report chosen ports in the final report.
- Browser verification must use the task-specific frontend URL and port.
- If the in-app browser shows a black screen, empty DOM, or unstable screenshots, fall back to Safari or Playwright/WebKit and report the fallback honestly.

## 6. Targeted verification matrix

Run checks that match the files changed. Do not over-fix unrelated failures from parallel sessions.

### Frontend UI task

- `cd apps/dsa-web && npm run check:design`
- Relevant Vitest page/component tests.
- `npm run lint`
- `npm run build`
- Safari or in-app desktop verification.
- 390px mobile verification.

### Home/report/history task

- Home surface tests, especially `HomeSurfacePage` tests.
- `reportNormalizer` tests.
- Relevant history/backend tests when backend payloads changed.
- Chat/Watchlist smoke tests if a shared normalizer changed.

### Admin task

- Relevant admin page tests.
- Relevant API tests.
- `npm run check:design`
- Desktop and 390px browser verification if visible UI changed.

### Backtest task

- Relevant backtest frontend tests.
- `tests/test_backtest*` only if backend or calculation code changed.
- Do not change calculations unless the task explicitly requires it.

### Portfolio task

- `PortfolioPage` tests.
- `tests/test_portfolio_service.py` if backend code changed.
- Verify accounting formulas remain unchanged unless the task explicitly requires formula changes.

### Market task

- `MarketOverviewPage` tests.
- Market/cache/freshness backend tests.
- Provider, fallback, and stale-status checks when provider behavior changed.

### Scanner/Watchlist task

- `UserScannerPage` or `WatchlistPage` tests.
- Scanner/backtest API tests only if backend code changed.
- Confirm scoring and backtest calculations remain unchanged unless explicitly in scope.

### DuckDB task

- Quant DuckDB tests.
- Portfolio/backtest regression tests when shared data paths changed.
- Verify disabled/no-write behavior.
- Do not commit generated DuckDB artifacts.

### Tooling/docs task

- Shell syntax checks if scripts changed.
- Markdown/document inspection for docs-only tasks.
- No browser verification unless visible UI changed.
- Avoid product code changes.

## 7. Design constitution and design guard

All frontend tasks must read:

```text
docs/frontend/visual-system.md
```

Run the design guard for frontend changes:

```bash
cd apps/dsa-web
npm run check:design
```

Current guard behavior blocks solid gray Tailwind backgrounds such as `bg-gray-*`, `bg-zinc-*`, `bg-slate-*`, and `bg-neutral-*`. Warning-only findings are advisory unless the task scope says otherwise.

For user-visible frontend work, raw/debug/provider/schema fields should be collapsed under developer details instead of exposed as primary UI. Chinese UI labels are the default except for tickers, provider names, metrics, currencies, and other domain terms normally shown in English.

## 8. Handling global build/ci blockers

Global build or CI may fail because unrelated dirty files from parallel sessions are incomplete. Do not fix unrelated dirty work.

When a global check fails:

- Report the exact failing command.
- Report the exact failing tests or build errors.
- Explain why the failure appears unrelated, if evidence supports that.
- Still run targeted checks for the current task.
- Treat real `ci_gate` failures as important; do not suppress or hide them.
- Separate optional provider/tool warnings from blocking product failures.

Expected optional or environment-dependent warnings include:

- `flake8` missing locally may be a local tool warning.
- `akshare` missing may be a provider/environment warning.
- `yfinance`, provider availability, or live data availability may affect provider tests depending on task scope.

## 9. Commit and push protocol

Before staging:

```bash
git status --short
git diff --stat
```

Then:

- Stage only task-related files with explicit paths.
- Avoid `git add .` unless the status is clean and the task scope is obvious.
- Use English commit messages.
- Push to `origin/main` when the task is complete and the task asked for push.
- Never commit generated artifacts, local databases, logs, coverage output, `test-results`, Playwright reports, screenshots, DuckDB files, or runtime caches.

## 10. Completion report format

Copy and fill this template:

```text
Commit:
- <hash> <English commit message>

Task summary:
- <what changed>

Files changed:
- <path>

Behavior changed:
- <user-visible or operator-visible behavior>

Behavior explicitly not changed:
- <formulas/scoring/API/product areas left untouched>

Tests/checks run:
- <command> -> <exact result>

Design guard:
- <command/result or "not applicable">

Browser verification:
- <URL/viewport/result or "not required for docs-only/no visible UI">

Dev server ports used:
- <ports or "none">

ci_gate:
- <result or unrelated blocker explanation or "not run">

Final git status --short:
- <output>

Parallel safety confirmation:
- Unrelated dirty files were not touched, staged, or committed.

Rollback:
- git revert <hash>
```

## 11. Active task tracking policy

- A task is considered in progress until the user provides a completion report.
- Once a completion report is provided, update task context before assigning or recommending more work.
- Recommend next tasks that avoid currently active file areas.
- Do not recommend tasks overlapping with unfinished sessions.

## 12. Common forbidden actions

- Do not discard unrelated work.
- Do not run `git reset --hard`.
- Do not clean untracked files globally.
- Do not kill shared servers casually.
- Do not broad-format source.
- Do not expose secrets or credentials.
- Do not write admin test credentials into docs; say "use the provided admin test credentials from the task prompt."
- Do not commit generated runtime artifacts.
- Do not change formulas, scoring, provider ranking, backtest calculations, or AI logic unless the task explicitly requires it.
