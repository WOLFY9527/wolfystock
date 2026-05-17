# WolfyStock Artifact Cleanup Policy

This policy defines which local artifacts are intentionally tracked, which are
generated and ignored, and when cleanup is safe.

It is a maintenance and operator guide only. It does not authorize deleting
artifacts during an active Codex task, and it does not replace task-specific
prompt boundaries.

## Ownership Model

Tracked repository assets:

- source files under current product/module ownership paths;
- intentional small fixtures and examples such as `tests/fixtures/` and
  `docs/examples/`;
- tracked documentation, audit guidance, and changelog entries that describe
  artifact handling or review outcomes.

Generated local artifacts:

- `reports/`, `artifacts/`, and `backtest_outputs/`;
- browser/test evidence such as `test-results/`, `playwright-report/`, and
  `apps/dsa-web/blob-report/`;
- visual screenshot captures under `screenshots/`;
- local audit/evidence bundles, temporary exports, runtime caches, and other
  ignored worktree-only outputs.

Do not reclassify generated artifacts as tracked fixtures by accident. If a new
fixture must be versioned, keep it small, deterministic, and intentionally
placed under an existing tracked fixture/examples path.

## Playwright Evidence

Playwright outputs are generated evidence, not repository authority.

- Keep `apps/dsa-web/test-results/`, `apps/dsa-web/playwright-report/`, and
  `apps/dsa-web/blob-report/` ignored.
- Use these outputs for local validation and operator handoff only.
- If durable evidence is needed in a tracked doc, summarize the result in a
  report/runbook/changelog instead of committing the raw artifact bundle.

## Visual Screenshots

Screenshots captured during UI checks or audits are generated artifacts.

- Keep `screenshots/` ignored.
- Do not treat stale screenshots as current truth when the live route or source
  can be inspected directly.
- If a screenshot is needed for a final report or review thread, attach it
  outside the tracked repo or summarize the verified outcome in a tracked doc.

## Audit Artifacts

Audit artifacts include temporary inventories, sanitized evidence exports,
local notes, packaged reviews, and other task-local outputs produced during
operator or Codex work.

- Treat them as generated unless the task explicitly asks for a tracked
  document.
- Prefer tracked summary docs over committing raw exports, archives, or local
  bundles.
- Do not move or delete source material as part of a cleanup-policy update.

## Cleanup Timing And Safety

Cleanup is allowed only after the related final report is accepted and the
artifact is no longer needed for the current worktree/branch.

Never:

- run broad `rm -rf` cleanup across repo storage paths;
- delete active worktree artifacts while Codex is still running in that
  worktree;
- delete artifacts during a docs-only policy task unless the prompt explicitly
  authorizes cleanup;
- delete sources or tracked fixture/example directories as a shortcut.

When cleanup is later approved, remove only the specific generated artifact path
that is known to be obsolete, and re-check the worktree before deleting shared
or branch-local evidence.

## Integration Follow-up

After this branch is merged or otherwise integrated, the integration owner
should clean this worktree/branch deliberately using the accepted final report
as the source of truth for which generated artifacts are safe to remove.
