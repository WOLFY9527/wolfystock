#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

print_header() {
  echo "==> task-preflight: $1"
}

print_git_upstream() {
  local upstream ahead behind

  if ! upstream="$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null)"; then
    echo "[INFO] Upstream: (none)"
    return 0
  fi

  read -r behind ahead < <(git rev-list --left-right --count "HEAD...${upstream}")
  echo "[INFO] Upstream: ${upstream} (ahead ${ahead}, behind ${behind})"
}

print_dirty_summary() {
  local dirty_count

  dirty_count="$(git status --porcelain=v1 --untracked-files=all | awk 'END { print NR }')"
  echo "[INFO] Dirty files: ${dirty_count}"

  if [[ "${dirty_count}" -eq 0 ]]; then
    echo "[INFO] Dirty categories: none"
    return 0
  fi

  echo "[INFO] Dirty categories:"
  git status --porcelain=v1 --untracked-files=all | awk '
    {
      path = substr($0, 4)
      sub(/ -> .*/, "", path)
      if (path == "") {
        path = "[root]"
      }
      split(path, parts, "/")
      top = parts[1]
      if (top == "") {
        top = "[root]"
      }
      count[top]++
    }
    END {
      for (top in count) {
        printf "%s\t%d\n", top, count[top]
      }
    }
  ' | sort -k2,2nr -k1,1 | while IFS=$'\t' read -r top count; do
    echo "[INFO]   - ${top}: ${count}"
  done

  echo "[WARN] Dirty files may belong to parallel Codex sessions. Do not stage unrelated files."
}

print_recent_commits() {
  echo "[INFO] Recent commits:"
  git log --oneline -5 | sed 's/^/[INFO]   /'
}

print_branch() {
  local branch

  branch="$(git branch --show-current)"
  if [[ -z "${branch}" ]]; then
    branch="(detached HEAD)"
  fi

  echo "[INFO] Branch: ${branch}"
}

print_header "repository state"
print_branch
print_git_upstream
print_dirty_summary
print_recent_commits
