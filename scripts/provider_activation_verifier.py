#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Print operator-only provider activation readiness."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.services.provider_activation_verifier import ProviderActivationVerifierService  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify local provider activation readiness without network calls or mutations.",
    )
    parser.add_argument(
        "--format",
        choices=("table", "json"),
        default="table",
        help="Output format.",
    )
    return parser


def _table(payload: dict[str, Any]) -> str:
    rows = [
        ("Capability", "Status", "Data class", "Blocked surfaces", "Next action"),
    ]
    for item in payload.get("capabilities") or []:
        rows.append(
            (
                str(item.get("capabilityId") or ""),
                str(item.get("status") or ""),
                str(item.get("dataClass") or ""),
                ", ".join(str(surface) for surface in item.get("blockedProductSurfaces") or []),
                str(item.get("adminNextAction") or ""),
            )
        )
    widths = [max(len(row[index]) for row in rows) for index in range(len(rows[0]))]
    lines = []
    for row_index, row in enumerate(rows):
        lines.append(" | ".join(value.ljust(widths[index]) for index, value in enumerate(row)))
        if row_index == 0:
            lines.append("-+-".join("-" * width for width in widths))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = ProviderActivationVerifierService().verify()
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print(_table(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
