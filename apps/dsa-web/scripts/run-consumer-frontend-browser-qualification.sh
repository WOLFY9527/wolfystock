#!/usr/bin/env bash
#
# Canonical, repository-owned entrypoint for strict consumer browser
# qualification of the WolfyStock consumer surfaces.
#
# The qualification matrix is owned here, never by the shell caller:
#   * strict qualification is always enabled;
#   * the `chromium` and `chromium-mobile` projects always run;
#   * exactly one complete spec authority is selected.
#
# Run it through the managed environment so the pinned Chromium executable and
# the run-scoped frontend output directory exist:
#
#   ./wolfy exec --profile test -- bash apps/dsa-web/scripts/run-consumer-frontend-browser-qualification.sh
#
# Modes:
#   (no arguments)  run the strict consumer qualification matrix
#   --print-plan    print the resolved selection as JSON and exit without Playwright
#   --list          collect the canonical cases without launching a browser
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

QUALIFICATION_SPEC="consumer-frontend-browser-qualification.spec.ts"
QUALIFICATION_PROJECTS=(chromium chromium-mobile)

# Plain assignments, not defaulted expansions: an ambient weak or unset value
# supplied by a caller must not be able to downgrade the qualified matrix.
STRICT_CONSUMER_FRONTEND_QUALIFICATION=1
WOLFYSTOCK_CONSUMER_BROWSER_QUALIFICATION_CANONICAL=1
export STRICT_CONSUMER_FRONTEND_QUALIFICATION WOLFYSTOCK_CONSUMER_BROWSER_QUALIFICATION_CANONICAL

print_usage() {
  cat <<'USAGE'
Usage: bash apps/dsa-web/scripts/run-consumer-frontend-browser-qualification.sh [--print-plan|--list]

Runs the strict consumer browser qualification matrix (every consumer
qualification case on chromium and chromium-mobile).

  --print-plan  Print the resolved qualification selection as JSON and exit.
  --list        Collect the canonical qualification cases without a browser.
  -h, --help    Show this message.

The matrix is fixed by this runner. Weakening flags such as --project, --grep,
--config, --workers are rejected; use the modes above instead.
USAGE
}

# Fail closed if strict qualification were ever dropped from this runner: a
# weaker matrix must never be published as consumer qualification evidence.
require_strict_selection() {
  if [[ "${STRICT_CONSUMER_FRONTEND_QUALIFICATION}" != "1" ]]; then
    echo "Refusing to run: STRICT_CONSUMER_FRONTEND_QUALIFICATION must be 1." >&2
    return 1
  fi
  if [[ "${WOLFYSTOCK_CONSUMER_BROWSER_QUALIFICATION_CANONICAL}" != "1" ]]; then
    echo "Refusing to run: WOLFYSTOCK_CONSUMER_BROWSER_QUALIFICATION_CANONICAL must be 1." >&2
    return 1
  fi
}

print_plan() {
  local json_projects=""
  local project
  for project in "${QUALIFICATION_PROJECTS[@]}"; do
    if [[ -n "${json_projects}" ]]; then
      json_projects+=","
    fi
    json_projects+="\"${project}\""
  done
  printf '{"schemaVersion":"wolfystock_consumer_browser_qualification_command_v1","spec":"%s","projects":[%s],"strict":"%s","canonical":"%s"}\n' \
    "${QUALIFICATION_SPEC}" \
    "${json_projects}" \
    "${STRICT_CONSUMER_FRONTEND_QUALIFICATION}" \
    "${WOLFYSTOCK_CONSUMER_BROWSER_QUALIFICATION_CANONICAL}"
}

PLAYWRIGHT_BIN="${APP_DIR}/node_modules/.bin/playwright"
QUALIFICATION_SPEC_PATH="${APP_DIR}/e2e/${QUALIFICATION_SPEC}"

MODE="run"
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    -h|--help)
      print_usage
      exit 0
      ;;
    --print-plan)
      MODE="print-plan"
      shift
      ;;
    --list)
      MODE="list"
      shift
      ;;
    *)
      echo "Refusing argument '$1': the canonical qualification matrix is fixed by this runner." >&2
      print_usage >&2
      exit 2
      ;;
  esac
done

require_strict_selection

if [[ ! -f "${QUALIFICATION_SPEC_PATH}" ]]; then
  echo "Missing canonical consumer qualification spec: ${QUALIFICATION_SPEC_PATH}" >&2
  exit 2
fi

if [[ "${MODE}" == "print-plan" ]]; then
  print_plan
  exit 0
fi

if [[ ! -x "${PLAYWRIGHT_BIN}" ]]; then
  echo "Playwright is unavailable at ${PLAYWRIGHT_BIN}." >&2
  echo "Run './wolfy bootstrap --ensure' and then invoke this runner through './wolfy exec --profile test'." >&2
  exit 127
fi

PROJECT_ARGS=()
for project in "${QUALIFICATION_PROJECTS[@]}"; do
  PROJECT_ARGS+=("--project=${project}")
done

PLAYWRIGHT_ARGS=(test "${PROJECT_ARGS[@]}" "${QUALIFICATION_SPEC}")
if [[ "${MODE}" == "list" ]]; then
  PLAYWRIGHT_ARGS+=(--list)
fi

cd "${APP_DIR}"
exec "${PLAYWRIGHT_BIN}" "${PLAYWRIGHT_ARGS[@]}"
