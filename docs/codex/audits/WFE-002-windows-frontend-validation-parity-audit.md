# WFE-002 Windows frontend validation parity audit

Task ID: WFE-002-AUDIT

Task title: Windows frontend validation parity audit

Mode: READ-ONLY-AUDIT with one explicitly allowed audit artifact.

Allowed artifact: `docs/codex/audits/WFE-002-windows-frontend-validation-parity-audit.md`

Observed workspace:

- cwd: `C:\Users\leeyi\worktrees\wfe-002-windows-validation-parity-audit`
- branch: `codex/wfe-002-windows-validation-parity-audit`
- shell: PowerShell launching Git Bash through `G:\Git\bin\sh.exe`
- date: 2026-06-06

Scope boundary:

- No source changes.
- No tests, configs, scripts, package files, lockfiles, CI, backend, API, or frontend behavior changes.
- `scripts/release_secret_scan.sh` was not edited.
- No repo shims were added.
- No npm scripts or React Doctor config were changed.

## Executive summary

Windows frontend validation is reliable when the gate is split into blocking
build/lint checks and non-blocking React Doctor diagnostics.

Blocking on Windows:

- `git diff --check`
- `G:\Git\bin\sh.exe ./scripts/release_secret_scan.sh`
- `npm --prefix apps/dsa-web run lint`
- `npm --prefix apps/dsa-web run build`

Non-blocking on Windows:

- `npx react-doctor@latest --json --json-compact --yes --no-score`
- `npx react-doctor@latest --score --yes`

React Doctor should be treated as advisory in this repo until a project policy
defines thresholds and failure semantics. The JSON command can return exit code
1 while still emitting valid diagnostics with `"ok": true`. The score command
completed successfully in this Windows audit, but it depends on external `npx`
package resolution and should not block release validation unless the task is
explicitly about React Doctor score enforcement.

## Command evidence

| Command | Result | Blocking classification | Notes |
| --- | --- | --- | --- |
| `git diff --check` | exit 0 | Blocking | No whitespace errors before writing this audit. Run again before commit. |
| `G:\Git\bin\sh.exe ./scripts/release_secret_scan.sh` | exit 0 | Blocking when it can run | Initial run found 0 changed files and no high-confidence secret patterns. |
| `npm --prefix apps/dsa-web run lint` | exit 0 | Blocking | `eslint .` completed successfully from PowerShell using `--prefix`. |
| `npm --prefix apps/dsa-web run build` | exit 0 | Blocking | `tsc -b && vite build` completed. Vite emitted existing large chunk warnings for `index` and `vendor-echarts`; these warnings did not fail the build. |
| `npx react-doctor@latest --json --json-compact --yes --no-score` | exit 1 | Non-blocking advisory | Emitted valid compact JSON with `"ok": true`, version `0.4.0`, 637 diagnostics, 121 errors, 516 warnings, 53 affected files, and no score. |
| `npx react-doctor@latest --score --yes` | exit 0 | Non-blocking advisory | Completed in this Windows run and printed score `60`. |

## React Doctor Windows interpretation

Use React Doctor as a diagnostic signal, not a hard gate, unless the task
explicitly asks to enforce it.

Recommended interpretation:

- JSON command exit 0: diagnostics collected; advisory result.
- JSON command exit 1 with valid JSON and `"ok": true`: diagnostics collected;
  advisory result, not a Windows validation failure.
- JSON command emits no parseable JSON, crashes before project discovery, or
  cannot resolve `npx`: environment/tooling failure; report as non-blocking
  unless the task is specifically about React Doctor availability.
- Score command exit 0: record score.
- Score command timeout: record timeout and rerun only if the task explicitly
  depends on score evidence.
- Score command exit non-zero with diagnostics still available from JSON:
  classify as non-blocking advisory.

## `shasum` Windows guidance

On this machine, Git Bash exposes:

- `/usr/bin/core_perl/shasum`
- `/usr/bin/sha1sum`
- `/usr/bin/perl`
- `/mingw64/bin/openssl`

Therefore `G:\Git\bin\sh.exe ./scripts/release_secret_scan.sh` completed
without a shim during this audit.

If another Windows machine fails with `shasum: command not found`, do not edit
the repo and do not add a shim under source control. Use a temporary directory
outside the repo and prepend it to `PATH` only for the scan process:

```powershell
G:\Git\bin\sh.exe -lc '
tmp="$(mktemp -d)"
printf "%s\n" "#!/usr/bin/env sh" "exec sha1sum \"\$@\"" > "$tmp/shasum"
chmod +x "$tmp/shasum"
PATH="$tmp:$PATH" ./scripts/release_secret_scan.sh
status=$?
rm -rf "$tmp"
exit "$status"
'
```

This works for the current script because `release_secret_scan.sh` pipes a
stable label into `shasum` and consumes the first whitespace-delimited hash.
`sha1sum` provides the same first-column shape for that use case.

If `sha1sum` is also unavailable, install/repair Git for Windows or run the
scan in an environment that provides Git Bash core utilities. Do not replace
the repo script as part of Windows frontend validation parity.

## Recommended Windows validation template

Use this template for future Windows React Doctor/frontend validation tasks:

```powershell
git diff --check
G:\Git\bin\sh.exe ./scripts/release_secret_scan.sh
npm --prefix apps/dsa-web run lint
npm --prefix apps/dsa-web run build
npx react-doctor@latest --json --json-compact --yes --no-score
npx react-doctor@latest --score --yes
```

Blocking policy:

- Stop on `git diff --check` failure.
- Stop on `release_secret_scan.sh` secret findings or scan execution failure
  that is not solely a local missing-`shasum` environment issue.
- Stop on lint failure.
- Stop on build failure.
- Do not stop on React Doctor diagnostics alone.
- Do not stop on React Doctor score timeout unless the task explicitly requires
  score evidence.

If `release_secret_scan.sh` fails only because `shasum` is unavailable:

1. confirm the failure is exactly `shasum: command not found`;
2. rerun once with the temporary non-repo shim above;
3. document both the original failure and the shim rerun result;
4. keep the final repo diff docs-only unless the task explicitly authorizes a
   script/config fix.

## Operational conclusion

Windows parity does not require source, script, npm, React Doctor config, or CI
changes from this audit. The reliable path is to keep lint/build/secret scan as
blocking gates and record React Doctor output as advisory evidence until a
separate policy task defines project-specific thresholds.
