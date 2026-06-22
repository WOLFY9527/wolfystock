---
applyTo: "README.md,docs/**,AGENTS.md,CLAUDE.md,.github/**,.claude/skills/**,scripts/**,docker/**"
---

# Governance Instructions

- `AGENTS.md` is the canonical AI collaboration rule source.
- `README.md` is the short human entrypoint.
- `docs/AI_PROJECT_MANUAL.md` is the generated comprehensive project handbook;
  edit `scripts/build_ai_project_manual.py` or the tiny canonical sources, then
  regenerate it.
- `docs/DOCS_INDEX.md` must stay tiny and point only to canonical files.
- Do not create broad indexes, archive lanes, task-report Markdown, or one-off
  acceptance snapshots unless a task explicitly requires that artifact.
- Keep `CLAUDE.md` as a symlink to `AGENTS.md`; keep `.github` instruction
  mirrors and `.claude/skills/` aligned with `AGENTS.md`.
- For docs/manual/governance changes, run `python scripts/build_ai_project_manual.py`,
  `python scripts/build_ai_project_manual.py --check`, and
  `python scripts/check_ai_assets.py`.
- Preserve opt-in auto-tag behavior (`#patch`, `#minor`, `#major`) unless a task
  explicitly updates release policy.
