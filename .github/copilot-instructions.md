# Repository Instructions

Canonical source: [`AGENTS.md`](../AGENTS.md).

If any instruction in this file conflicts with `AGENTS.md`, follow `AGENTS.md`.
`CLAUDE.md` must remain a symlink to `AGENTS.md`. Repository skills retained for
Claude-compatible workflows live in `.claude/skills/`.

## Core Rules

- Use `README.md` for the human entrypoint and `docs/AI_PROJECT_MANUAL.md` for
  the comprehensive project handbook.
- Respect directory boundaries:
  - Backend: `src/`, `data_provider/`, `api/`, `bot/`
  - Web: `apps/dsa-web/`
  - Desktop: `apps/dsa-desktop/`
  - Deployment/workflows: `scripts/`, `.github/workflows/`, `docker/`
- Do not run `git commit`, `git tag`, `git push`, `git merge`, or `git rebase`
  without explicit task authorization.
- Do not hardcode secrets, accounts, tokens, ports, model names, private URLs,
  or absolute environment-specific paths.
- Reuse existing modules, configuration entrypoints, scripts, and tests instead
  of adding parallel implementations.
- Do not modify provider order, fallback behavior, auth, accounting, broker,
  DB migrations, package/config files, CI, or other protected domains unless the
  task explicitly scopes them.

## Validation

- Backend: prefer `./scripts/ci_gate.sh`; otherwise run `python -m py_compile`
  on changed files plus the closest deterministic tests.
- Web: `cd apps/dsa-web && npm ci && npm run lint && npm run build` when
  frontend source changes.
- Desktop: build Web first, then desktop when feasible.
- AI/docs governance: run `python scripts/build_ai_project_manual.py --check`
  and `python scripts/check_ai_assets.py`.
