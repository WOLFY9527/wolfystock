"""Request-correlation lifecycle, isolation, and privacy contracts."""

from __future__ import annotations

import asyncio
import re
import unittest
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.middlewares.error_handler import add_error_handlers
from api.request_context import (
    REQUEST_ID_HEADER,
    RequestCorrelationMiddleware,
    get_request_id,
)


_REQUEST_ID_RE = re.compile(r"^[a-f0-9]{32}$")


def _probe_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestCorrelationMiddleware)

    @app.get("/api/sync-probe")
    def sync_probe() -> dict[str, str | None]:
        return {"request_id": get_request_id()}

    @app.get("/api/error")
    async def error_probe() -> None:
        raise HTTPException(status_code=503, detail="bounded failure")

    @app.get("/api/exception")
    async def exception_probe() -> None:
        raise RuntimeError("internal failure")

    add_error_handlers(app)
    return app


class RequestContextTestCase(unittest.TestCase):
    def test_success_header_logger_and_untrusted_inputs_use_one_server_owned_id(self) -> None:
        client = TestClient(_probe_app())
        injected = "token=raw-secret-forged-log-line"
        with self.assertLogs("api.request_context", level="INFO") as captured:
            first = client.get(
                "/api/sync-probe?query_id=domain-query",
                headers={
                    REQUEST_ID_HEADER: injected,
                    "Idempotency-Key": "idempotency-secret",
                    "Authorization": "Bearer access-token-secret",
                    "Cookie": "session=raw-session-secret",
                },
            )
            second = client.get("/api/sync-probe")

        first_id = first.headers[REQUEST_ID_HEADER]
        second_id = second.headers[REQUEST_ID_HEADER]
        self.assertRegex(first_id, _REQUEST_ID_RE)
        self.assertRegex(second_id, _REQUEST_ID_RE)
        self.assertEqual(first.json()["request_id"], first_id)
        self.assertEqual(second.json()["request_id"], second_id)
        self.assertNotEqual(first_id, second_id)
        self.assertIsNone(get_request_id())
        joined_logs = "\n".join(captured.output)
        self.assertIn(first_id, joined_logs)
        for forbidden in (
            injected,
            "forged-log-line",
            "domain-query",
            "idempotency-secret",
            "access-token-secret",
            "raw-session-secret",
        ):
            self.assertNotIn(forbidden, joined_logs)

    def test_error_and_slow_request_records_share_response_id(self) -> None:
        client = TestClient(_probe_app(), raise_server_exceptions=False)
        with patch("src.services.execution_log_service.ExecutionLogService") as service_class:
            error = client.get("/api/error")
            error_call = service_class.return_value.record_api_request.call_args.kwargs

        self.assertEqual(error.status_code, 503)
        self.assertEqual(error_call["request_id"], error.headers[REQUEST_ID_HEADER])
        self.assertEqual(error_call["status_code"], 503)

        with (
            patch("api.request_context.SLOW_REQUEST_THRESHOLD_MS", -1.0),
            patch("src.services.execution_log_service.ExecutionLogService") as service_class,
        ):
            slow = client.get("/api/sync-probe")
            slow_call = service_class.return_value.record_api_request.call_args.kwargs

        self.assertEqual(slow.status_code, 200)
        self.assertEqual(slow_call["request_id"], slow.headers[REQUEST_ID_HEADER])
        self.assertEqual(slow_call["status_code"], 200)
        self.assertGreaterEqual(slow_call["duration_ms"], 0)
        self.assertIsNone(get_request_id())

    def test_general_exception_response_and_log_retain_id_then_clear_context(self) -> None:
        client = TestClient(_probe_app(), raise_server_exceptions=False)
        with (
            patch("src.services.execution_log_service.ExecutionLogService") as service_class,
            self.assertLogs(level="ERROR") as captured,
        ):
            response = client.get("/api/exception")

        request_id = response.headers[REQUEST_ID_HEADER]
        self.assertEqual(response.status_code, 500)
        self.assertRegex(request_id, _REQUEST_ID_RE)
        self.assertEqual(
            service_class.return_value.record_api_request.call_args.kwargs["request_id"],
            request_id,
        )
        self.assertTrue(any(request_id in line for line in captured.output))
        self.assertIsNone(get_request_id())

    def test_concurrent_requests_do_not_cross_contaminate(self) -> None:
        async def exercise() -> dict[str, dict[str, str | None]]:
            ready_count = 0
            release = asyncio.Event()
            observed: dict[str, dict[str, str | None]] = {}

            async def app(scope, _receive, send) -> None:
                nonlocal ready_count
                label = scope["path"].rsplit("/", 1)[-1]
                first = get_request_id()
                ready_count += 1
                if ready_count == 2:
                    release.set()
                await release.wait()
                second = get_request_id()
                observed[label] = {"first": first, "second": second, "header": None}
                await send({"type": "http.response.start", "status": 200, "headers": []})
                await send({"type": "http.response.body", "body": b""})

            middleware = RequestCorrelationMiddleware(app)

            async def run_one(label: str) -> None:
                async def receive() -> dict[str, object]:
                    return {"type": "http.request", "body": b"", "more_body": False}

                async def send(message) -> None:
                    if message["type"] == "http.response.start":
                        headers = {name.decode(): value.decode() for name, value in message["headers"]}
                        observed[label]["header"] = headers[REQUEST_ID_HEADER.lower()]

                await middleware(
                    {
                        "type": "http",
                        "method": "GET",
                        "path": f"/api/concurrent/{label}",
                        "headers": [],
                    },
                    receive,
                    send,
                )

            await asyncio.gather(run_one("one"), run_one("two"))
            return observed

        observed = asyncio.run(exercise())
        self.assertEqual(observed["one"]["first"], observed["one"]["second"])
        self.assertEqual(observed["two"]["first"], observed["two"]["second"])
        self.assertEqual(observed["one"]["first"], observed["one"]["header"])
        self.assertEqual(observed["two"]["first"], observed["two"]["header"])
        self.assertNotEqual(observed["one"]["first"], observed["two"]["first"])
        self.assertIsNone(get_request_id())

    def test_exception_before_response_resets_context(self) -> None:
        observed_request_id: str | None = None

        async def failing_app(_scope, _receive, _send) -> None:
            nonlocal observed_request_id
            observed_request_id = get_request_id()
            raise RuntimeError("boom")

        async def exercise() -> None:
            middleware = RequestCorrelationMiddleware(failing_app)

            async def receive() -> dict[str, object]:
                return {"type": "http.request", "body": b"", "more_body": False}

            async def send(_message) -> None:
                return None

            with patch("src.services.execution_log_service.ExecutionLogService"):
                with self.assertRaises(RuntimeError):
                    await middleware(
                        {"type": "http", "method": "GET", "path": "/api/fail", "headers": []},
                        receive,
                        send,
                    )

        asyncio.run(exercise())
        self.assertRegex(observed_request_id or "", _REQUEST_ID_RE)
        self.assertIsNone(get_request_id())


if __name__ == "__main__":
    unittest.main()
