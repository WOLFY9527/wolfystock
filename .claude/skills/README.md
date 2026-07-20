# Repository Claude Skills

This directory contains the repository-level skill assets retained for
Claude-compatible workflows.

- Rule source: repository root `AGENTS.md`
- Compatibility entry: root `CLAUDE.md`, which must be a symlink to `AGENTS.md`
- Project task router: `docs/README.md`
- Generated catalog: `docs/generated/AI_PROJECT_MANUAL.md` (navigation only)
- Local review artifacts: `.claude/reviews/` and similar generated evidence are
  local artifacts, not rule sources

Keep these skills aligned with `AGENTS.md`. Do not add parallel skill mirrors or
new Markdown report lanes unless a task explicitly requires them.
