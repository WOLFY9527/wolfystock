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


if __name__ == "__main__":
    unittest.main()
