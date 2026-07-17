#!/usr/bin/env python3
"""Managed child process used by wolfy development orchestration."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


class RunIdentityApplication:
    def __init__(self, application, run_id: str) -> None:
        self.application = application
        self.payload = json.dumps({"runId": run_id}, sort_keys=True, separators=(",", ":")).encode("utf-8")

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") == "http" and scope.get("path") == "/__wolfy__/ready":
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(self.payload)).encode("ascii")),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": self.payload})
            return
        await self.application(scope, receive, send)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    subparsers = parser.add_subparsers(dest="service", required=True)
    backend = subparsers.add_parser("backend")
    endpoint = backend.add_mutually_exclusive_group(required=True)
    endpoint.add_argument("--fd", type=int)
    endpoint.add_argument("--port", type=int)
    args = parser.parse_args()
    if args.service != "backend":
        return 2
    repository_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repository_root))
    import uvicorn
    from api.app import app

    options = {"host": "127.0.0.1", "log_level": "warning"}
    if args.fd is not None:
        options["fd"] = args.fd
    else:
        options["port"] = args.port
    uvicorn.run(RunIdentityApplication(app, args.run_id), **options)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
