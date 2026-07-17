#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
case "${1:-}" in
  --check)
    exec "${ROOT_DIR}/wolfy" env verify
    ;;
  --apply)
    exec "${ROOT_DIR}/wolfy" bootstrap --ensure
    ;;
  *)
    printf '%s\n' 'usage: scripts/bootstrap_worktree.sh --check|--apply' >&2
    exit 2
    ;;
esac
