# -*- coding: utf-8 -*-
"""Targeted tests for crypto realtime websocket degradation hardening."""

from __future__ import annotations

import asyncio
import collections
import unittest
from unittest.mock import patch


class CryptoRealtimeWebsocketHardeningTestCase(unittest.TestCase):
    def test_safe_client_connection_handles_connection_lost_before_connection_made(self) -> None:
        from src.services.crypto_realtime_service import _get_safe_websocket_client_connection_class
        from websockets.protocol import CLOSED

        safe_connection_class = _get_safe_websocket_client_connection_class()
        self.assertIsNotNone(safe_connection_class)

        loop = asyncio.new_event_loop()
        try:
            connection = object.__new__(safe_connection_class)
            protocol = type(
                "ProtocolStub",
                (),
                {
                    "receive_eof": lambda self: None,
                    "state": CLOSED,
                    "close_exc": ConnectionResetError("reset by peer"),
                },
            )()
            connection.protocol = protocol
            connection.pending_pings = {}
            connection.keepalive_task = None
            connection.connection_lost_waiter = loop.create_future()
            connection.paused = False
            connection.drain_waiters = collections.deque()

            connection.connection_lost(ConnectionResetError("reset by peer"))

            self.assertTrue(connection.connection_lost_waiter.done())
        finally:
            loop.close()

    def test_safe_client_connection_handles_missing_terminate_pending_pings_compatibly(self) -> None:
        from src.services.crypto_realtime_service import _get_safe_websocket_client_connection_class
        from websockets.protocol import CLOSED

        safe_connection_class = _get_safe_websocket_client_connection_class()
        self.assertIsNotNone(safe_connection_class)

        class CompatibilityConnection(safe_connection_class):
            def __getattribute__(self, name: str):
                if name == "terminate_pending_pings":
                    raise AttributeError(name)
                return super().__getattribute__(name)

        loop = asyncio.new_event_loop()
        try:
            connection = object.__new__(CompatibilityConnection)
            protocol = type(
                "ProtocolStub",
                (),
                {
                    "receive_eof": lambda self: None,
                    "state": CLOSED,
                    "close_exc": ConnectionResetError("reset by peer"),
                },
            )()
            connection.protocol = protocol
            connection.pending_pings = {}
            connection.keepalive_task = None
            connection.connection_lost_waiter = loop.create_future()
            connection.paused = False
            connection.drain_waiters = collections.deque()

            connection.connection_lost(ConnectionResetError("reset by peer"))

            self.assertTrue(connection.connection_lost_waiter.done())
        finally:
            loop.close()

    def test_binance_provider_uses_safe_create_connection_when_supported(self) -> None:
        from src.services.crypto_realtime_service import BinanceWsProvider, _get_safe_websocket_client_connection_class

        provider = BinanceWsProvider()
        safe_connection_class = _get_safe_websocket_client_connection_class()
        self.assertIsNotNone(safe_connection_class)

        def connect_stub(uri: str, *, create_connection=None, **kwargs):
            return None

        kwargs = provider._build_connect_kwargs(connect_stub)

        self.assertEqual(kwargs["create_connection"], safe_connection_class)

    def test_binance_provider_skips_safe_create_connection_when_unsupported(self) -> None:
        from src.services.crypto_realtime_service import BinanceWsProvider

        provider = BinanceWsProvider()

        def legacy_connect_stub(uri: str, *, ping_interval=None, ping_timeout=None, close_timeout=None, ssl=None):
            return None

        kwargs = provider._build_connect_kwargs(legacy_connect_stub)

        self.assertNotIn("create_connection", kwargs)

    def test_connection_reset_failure_enters_degraded_backoff(self) -> None:
        from src.services.crypto_realtime_service import CryptoRealtimeProvider, CryptoRealtimeService

        class ResettingProvider(CryptoRealtimeProvider):
            async def connect(self):
                if False:
                    yield {}
                raise ConnectionResetError("reset by peer")

        service = CryptoRealtimeService(provider=ResettingProvider(), auto_start=False, reconnect_delay_seconds=0.01)
        sleep_delays: list[float] = []

        async def fake_sleep(delay: float) -> None:
            sleep_delays.append(delay)
            service.stop()

        with patch("src.services.crypto_realtime_service.asyncio.sleep", side_effect=fake_sleep):
            asyncio.run(service._run_forever())

        status = service.get_stream_status()
        self.assertEqual(status["state"], "degraded")
        self.assertEqual(status["reason"], "connection_failed")
        self.assertEqual(status["failureCount"], 1)
        self.assertEqual(sleep_delays, [0.01])

    def test_disabled_env_does_not_auto_start_service_singleton(self) -> None:
        import src.services.crypto_realtime_service as crypto_realtime_service

        original_service = crypto_realtime_service._service
        crypto_realtime_service._service = None
        try:
            with patch.dict("os.environ", {"CRYPTO_REALTIME_ENABLED": "0"}, clear=False):
                with patch.object(
                    crypto_realtime_service.CryptoRealtimeService,
                    "start",
                    side_effect=AssertionError("crypto realtime should not auto-start when disabled"),
                ):
                    service = crypto_realtime_service.get_crypto_realtime_service()

            self.assertFalse(service._started)
            self.assertFalse(service._stop_event.is_set())
        finally:
            crypto_realtime_service._service = original_service


if __name__ == "__main__":
    unittest.main()
