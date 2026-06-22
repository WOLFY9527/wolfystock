<!--
WolfyStock Reflect-Linear UI replacement document.
Source of truth image: docs/design/reference/wolfystock-reflect-linear-home-mockup.png
This document intentionally supersedes older deep-space / terminal / bento / generic Linear UI wording.
-->

# WolfyStock Frontend UI Documentation Replacement Map

Status: archived historical replacement note. The file paths and install
commands below describe the original Reflect-Linear docs replacement pack and
are retained as provenance only. Current frontend authority lives in
`docs/frontend/`.

This pack replaces the canonical frontend UI/UX design documents with the Reflect-Linear Research OS direction.

## Included files

```text
docs/design/reference/wolfystock-reflect-linear-home-mockup.png
docs/design/WOLFYSTOCK_REFLECT_LINEAR_VISUAL_SPEC.md
docs/design/wolfystock-canonical-ui-primitives.md
docs/codex/WOLFYSTOCK_LINEAR_OS_DESIGN_LANGUAGE.md
docs/codex/WOLFYSTOCK_FRONTEND_SURFACE_USAGE.md
docs/codex/WOLFYSTOCK_FRONTEND_ROUTE_TEMPLATES.md
docs/codex/CODEX_FRONTEND_DESIGN_CONSTITUTION.md
docs/codex/WOLFYSTOCK_FRONTEND_VALIDATION_PLAYBOOK.md
```

## Replacement goal

Remove ambiguity from older UI guidance. The approved visual target is the uploaded/gen mockup:

```text
docs/design/reference/wolfystock-reflect-linear-home-mockup.png
```

Future frontend tasks should not continue to follow old language such as:

```text
deep-space terminal
ghost UI
OLED terminal
bento dashboard
no cards
card-first dashboard
generic Linear only
```

The new rule is:

```text
Reflect-Linear Research OS: calm dark finance UI, low-saturation violet atmosphere, thin borders, subtle glass, fixed regions, controlled panels, no uncontrolled card sprawl.
```

## Recommended install commands

```bash
cd /Users/yehengli/daily_stock_analysis

unzip ~/Downloads/wolfystock_reflect_linear_ui_md_replace.zip -d /tmp/wolfystock_reflect_linear_ui_md_replace
cp -R /tmp/wolfystock_reflect_linear_ui_md_replace/docs/codex docs/
cp -R /tmp/wolfystock_reflect_linear_ui_md_replace/docs/design docs/

git status --short
git diff -- docs/codex docs/design
```

## Recommended validation

```bash
git diff --check -- docs/codex docs/design
./scripts/release_secret_scan.sh
```

## Recommended commit

```bash
git add docs/codex/WOLFYSTOCK_LINEAR_OS_DESIGN_LANGUAGE.md \
        docs/codex/WOLFYSTOCK_FRONTEND_SURFACE_USAGE.md \
        docs/codex/WOLFYSTOCK_FRONTEND_ROUTE_TEMPLATES.md \
        docs/codex/CODEX_FRONTEND_DESIGN_CONSTITUTION.md \
        docs/codex/WOLFYSTOCK_FRONTEND_VALIDATION_PLAYBOOK.md \
        docs/design/WOLFYSTOCK_REFLECT_LINEAR_VISUAL_SPEC.md \
        docs/design/wolfystock-canonical-ui-primitives.md \
        docs/design/reference/wolfystock-reflect-linear-home-mockup.png

git commit -m "docs(design): set Reflect Linear UI source of truth"
git push origin main
```
