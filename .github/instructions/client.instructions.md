---
applyTo: "apps/dsa-web/**,apps/dsa-desktop/**,scripts/run-desktop.ps1,scripts/build-desktop*.ps1,scripts/build-*.sh"
---

# Client Instructions

- Follow `AGENTS.md`; use `docs/AI_PROJECT_MANUAL.md` for frontend surfaces,
  no-advice, data-readiness, and protected-domain context.
- Preserve the existing Vite + React web structure and Electron desktop runtime
  assumptions; reuse current API/state patterns instead of adding parallel client
  abstractions.
- Keep consumer copy free of raw provider/cache/schema/debug/credential/internal
  terms unless the route is explicitly an admin/operator diagnostic surface.
- If a change affects API fields, auth state, route behavior, Markdown/chart
  rendering, local backend startup, or report payloads, assess both Web and
  Desktop compatibility.
- Validate Web changes with `cd apps/dsa-web && npm ci && npm run lint &&
  npm run build` when feasible. For visual changes, add route/browser evidence.
- Validate Desktop changes by building Web first, then `apps/dsa-desktop`; if
  platform limits prevent full Electron validation, call out the exact risk.
