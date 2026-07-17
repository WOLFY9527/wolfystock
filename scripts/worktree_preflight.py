#!/usr/bin/env python3
"""Thin compatibility delegate to the repository-owned wolfy authority."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.environment.cli import main as wolfy_main  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    values = list(argv if argv is not None else sys.argv[1:])
    if values == ["bootstrap", "--check"]:
        return wolfy_main(["env", "verify"])
    if values == ["bootstrap", "--apply"]:
        return wolfy_main(["bootstrap", "--ensure"])
    print("worktree_preflight.py accepts only bootstrap --check or bootstrap --apply", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
