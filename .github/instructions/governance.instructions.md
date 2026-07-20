---
applyTo: "README.md,docs/**,AGENTS.md,CLAUDE.md,.github/**,.claude/skills/**,scripts/**,docker/**"
---

# Governance Instructions

- `AGENTS.md` is the canonical AI collaboration rule source.
- `README.md` is the short human entrypoint.
- `docs/documentation-manifest.json` owns document classification, authority,
  routing, generated outputs, and temporary-evidence lifecycle.
- `docs/README.md` and `docs/generated/AI_PROJECT_MANUAL.md` are generated
  navigation. Edit the manifest or canonical source, then regenerate.
- Do not create archive lanes, compatibility copies, unregistered Markdown, or
  one-off acceptance snapshots without an explicit lifecycle owner.
- Keep `CLAUDE.md` as a symlink to `AGENTS.md`; keep `.github` instruction
  mirrors and `.claude/skills/` aligned with `AGENTS.md`.
- For docs/manual/governance changes, run `python scripts/build_ai_project_manual.py`,
  `python scripts/check_documentation.py`,
  `python scripts/build_ai_project_manual.py --check`, and
  `python scripts/check_ai_assets.py`.
- Preserve opt-in auto-tag behavior (`#patch`, `#minor`, `#major`) unless a task
  explicitly updates release policy.
