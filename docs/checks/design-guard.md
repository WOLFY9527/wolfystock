# WolfyStock Design Guard

The frontend design guard turns `CODEX_FRONTEND_DESIGN_CONSTITUTION.md` into a conservative automated check for production source.

Run it from the web app:

```bash
cd apps/dsa-web
npm run check:design
```

## Blocking Rules

- `no-solid-gray-bg`: blocks Tailwind solid gray background surfaces such as `bg-gray-*`, `bg-zinc-*`, `bg-slate-*`, and `bg-neutral-*`.

The gray rule intentionally does not block `text-gray-*`, `border-gray-*`, or `ring-gray-*`; the design constitution target is solid background surfaces.

## Warning Rules

- `raw-debug-copy`: warns on obvious visible raw/debug/provider/schema copy such as `provider_down`, `provider_error`, `SCHEMA`, `system prompt`, or `API key`.
- `localized-ui-copy`: warns on likely visible English fallback/status labels such as `UNKNOWN`, `Key Metrics`, `Data Quality`, `Advanced Details`, and `Provider Error`.
- `native-ui`: warns on clear default/native UI risks, including scroll containers without a stealth scrollbar utility and native controls without visible styling.

Warnings are non-blocking because the current source still has legacy surfaces that need visual review before broad cleanup. New code should avoid adding warning-only findings.

## Exceptions

Prefer fixing the source instead of adding exceptions. If a legitimate exception is needed, keep it narrow and local in `apps/dsa-web/scripts/check-design-constitution.mjs`, with a comment explaining why the visible UI is acceptable.

Developer-only raw diagnostics are allowed when they are clearly inside collapsed developer details, for example a `<details>` section labeled `开发者字段`, `原始诊断`, `数据质量`, `执行假设`, or `调试信息`.

## Scope

The guard scans production frontend source under `apps/dsa-web/src` for `.tsx`, `.ts`, and `.css` files. It excludes tests, build output, coverage, Playwright output, generated artifacts, images/assets, and dependency folders.

This guard is intentionally conservative. It catches repeatable design regressions early, but it does not replace browser or Safari visual review for actual UI changes.
