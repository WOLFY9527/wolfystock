# -*- coding: utf-8 -*-
"""Realtime crypto quotes backed by exchange websocket streams."""

from __future__ import annotations

import asyncio
import collections
import inspect
import json
import logging
import os
import ssl
import threading
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator, Dict, Iterable, Optional

from src.services.market_cache import MARKET_CACHE_TTLS, market_cache


logger = logging.getLogger(__name__)
CN_TZ = timezone(timedelta(hours=8))
_SAFE_WEBSOCKET_CLIENT_CONNECTION_CLASS: Any = ...


def _now() -> datetime:
    return datetime.now(CN_TZ)


def _now_iso() -> str:
    return _now().isoformat(timespec="seconds")


def _parse_time(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=CN_TZ)
    return parsed.astimezone(CN_TZ)


def _clean_number(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def _get_safe_websocket_client_connection_class() -> Optional[type[Any]]:
    global _SAFE_WEBSOCKET_CLIENT_CONNECTION_CLASS
    if _SAFE_WEBSOCKET_CLIENT_CONNECTION_CLASS is ...:
        try:
            from websockets.asyncio.client import ClientConnection
        except Exception:
            _SAFE_WEBSOCKET_CLIENT_CONNECTION_CLASS = None
            return None

        class SafeCryptoRealtimeClientConnection(ClientConnection):
            def connection_lost(self, exc: Exception | None) -> None:
                if hasattr(self, "recv_messages"):
                    super().connection_lost(exc)
                    return

                # websockets 16 may call connection_lost() before connection_made()
                # completes on some degraded connect/reset paths.
                if not hasattr(self, "recv_exc"):
                    self.recv_exc = None
                self.protocol.receive_eof()
                self.set_recv_exc(exc)
                self._terminate_pending_pings_compat(exc)

                if self.keepalive_task is not None:
                    self.keepalive_task.cancel()

                if not self.connection_lost_waiter.done():
                    self.connection_lost_waiter.set_result(None)

                if getattr(self, "paused", False):
                    self.paused = False
                    for waiter in getattr(self, "drain_waiters", collections.deque()):
                        if waiter.done():
                            continue
                        if exc is None:
                            waiter.set_result(None)
                        else:
                            waiter.set_exception(exc)

            def _terminate_pending_pings_compat(self, exc: Exception | None) -> None:
                terminate_pending_pings = getattr(type(self), "terminate_pending_pings", None)
                if callable(terminate_pending_pings):
                    terminate_pending_pings(self)
                    return

                pending_pings = getattr(self, "pending_pings", None)
                if not pending_pings:
                    return

                close_exc = getattr(self.protocol, "close_exc", None) or exc
                for pong_received, _ping_timestamp in pending_pings.values():
                    if not pong_received.done():
                        pong_received.set_exception(close_exc)
                    pong_received.cancel()
                pending_pings.clear()

        _SAFE_WEBSOCKET_CLIENT_CONNECTION_CLASS = SafeCryptoRealtimeClientConnection

    return _SAFE_WEBSOCKET_CLIENT_CONNECTION_CLASS


class CryptoRealtimeProvider(ABC):
    """Provider interface for realtime crypto quote streams."""

    async def subscribe(self, symbols: Iterable[str]) -> None:
        """Subscribe to symbols when a provider requires an explicit subscribe frame."""

    def on_tick(self, raw_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalize one provider tick payload."""
        return raw_payload

    @abstractmethod
    async def connect(self) -> AsyncIterator[Dict[str, Any]]:
        """Yield normalized ticks with symbol, price, change, and changePercent."""


class BinanceWsProvider(CryptoRealtimeProvider):
    """Minimal Binance ticker websocket provider for BTC/ETH/BNB."""

    STREAM_SYMBOLS = {
        "BTCUSDT": ("BTC", "Bitcoin"),
        "ETHUSDT": ("ETH", "Ethereum"),
        "BNBUSDT": ("BNB", "BNB"),
    }

    def __init__(self, symbols: Optional[Iterable[str]] = None) -> None:
        streams = symbols or ["btcusdt@ticker", "ethusdt@ticker", "bnbusdt@ticker"]
        self.streams = [str(stream).lower() for stream in streams]

    async def connect(self) -> AsyncIterator[Dict[str, Any]]:
        import websockets

        stream_path = "/".join(self.streams)
        url = f"wss://stream.binance.com:9443/stream?streams={stream_path}"
        async with websockets.connect(url, **self._build_connect_kwargs(websockets.connect)) as websocket:
            async for raw_message in websocket:
                payload = json.loads(raw_message)
                data = payload.get("data") if isinstance(payload, dict) else None
                if not isinstance(data, dict):
                    continue
                tick = self._parse_ticker(data)
                if tick:
                    yield tick

    def _build_connect_kwargs(self, connect_callable: Any) -> Dict[str, Any]:
        connect_kwargs: Dict[str, Any] = {
            "ping_interval": 20,
            "ping_timeout": 20,
            "close_timeout": 5,
            "ssl": self._ssl_context(),
        }
        try:
            parameters = inspect.signature(connect_callable).parameters
        except (TypeError, ValueError):
            parameters = {}
        safe_connection_class = _get_safe_websocket_client_connection_class()
        if safe_connection_class is not None and "create_connection" in parameters:
            connect_kwargs["create_connection"] = safe_connection_class
        return connect_kwargs

    def _ssl_context(self) -> ssl.SSLContext:
        try:
            import certifi

            return ssl.create_default_context(cafile=certifi.where())
        except Exception:
            return ssl.create_default_context()

    def _parse_ticker(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        stream_symbol = str(data.get("s") or "").upper()
        label = self.STREAM_SYMBOLS.get(stream_symbol)
        if not label:
            return None
        price = _clean_number(data.get("c"))
        if price is None:
            return None
        event_time = _clean_number(data.get("E"))
        as_of = (
            datetime.fromtimestamp(event_time / 1000, tz=timezone.utc).astimezone(CN_TZ).isoformat(timespec="seconds")
            if event_time
            else _now_iso()
        )
        return {
            "symbol": label[0],
            "name": label[1],
            "price": price,
            "change": _clean_number(data.get("p")),
            "changePercent": _clean_number(data.get("P")),
            "asOf": as_of,
        }


class CryptoRealtimeService:
    """Keep a throttled in-memory crypto snapshot and mirror it into MarketCache."""

    SYMBOL_LABELS = {
        "BTC": "Bitcoin",
        "ETH": "Ethereum",
        "BNB": "BNB",
    }

    def __init__(
        self,
        provider: Optional[CryptoRealtimeProvider] = None,
        *,
        auto_start: bool = True,
        throttle_seconds: float = 1.0,
        stale_after_seconds: int = 30,
        reconnect_delay_seconds: float = 5.0,
        max_reconnect_delay_seconds: float = 60.0,
    ) -> None:
        self.provider = provider or BinanceWsProvider()
        self.throttle_seconds = throttle_seconds
        self.stale_after_seconds = stale_after_seconds
        self.reconnect_delay_seconds = reconnect_delay_seconds
        self.max_reconnect_delay_seconds = max(max_reconnect_delay_seconds, reconnect_delay_seconds)
        self._lock = threading.RLock()
        self._ticks: Dict[str, Dict[str, Any]] = {}
        self._last_snapshot: Optional[Dict[str, Any]] = None
        self._last_published_at: Optional[datetime] = None
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._started = False
        self._condition = threading.Condition(self._lock)
        self._stream_state = "idle"
        self._stream_reason: Optional[str] = None
        self._stream_warning: Optional[str] = None
        self._failure_count = 0
        self._next_retry_at: Optional[datetime] = None
        if auto_start:
            self.start()

    def start(self) -> None:
        if self._started or self._stop_event.is_set():
            return
        self._started = True
        self._thread = threading.Thread(target=self._run_background_loop, name="crypto-realtime", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        with self._condition:
            self._condition.notify_all()

    def handle_tick(self, tick: Dict[str, Any]) -> None:
        symbol = str(tick.get("symbol") or "").upper()
        if symbol not in self.SYMBOL_LABELS:
            return
        price = _clean_number(tick.get("price") if "price" in tick else tick.get("value"))
        if price is None:
            return
        as_of = _parse_time(tick.get("asOf") or tick.get("updatedAt")) or _now()
        item = {
            "symbol": symbol,
            "name": tick.get("name") or self.SYMBOL_LABELS[symbol],
            "label": tick.get("name") or self.SYMBOL_LABELS[symbol],
            "value": round(price, 2),
            "price": round(price, 2),
            "change": _clean_number(tick.get("change")) or 0.0,
            "changePercent": _clean_number(tick.get("changePercent")) or 0.0,
            "sparkline": self._next_sparkline(symbol, price),
            "trend": self._next_sparkline(symbol, price),
            "unit": "USD",
            "source": "binance_ws",
            "sourceLabel": "Binance WS",
            "freshness": "live",
            "isFallback": False,
            "asOf": as_of.isoformat(timespec="seconds"),
            "updatedAt": _now_iso(),
            "last_update": as_of.isoformat(timespec="seconds"),
        }
        with self._condition:
            self._mark_stream_live_locked()
            self._ticks[symbol] = item
            snapshot = self._build_snapshot_locked()
            self._last_snapshot = snapshot
            self._last_published_at = _now()
            market_cache.set("crypto", snapshot, MARKET_CACHE_TTLS.get("crypto", 15))
            self._condition.notify_all()

    def get_snapshot(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            if not self._last_snapshot:
                return None
            return self._snapshot_with_freshness_locked(dict(self._last_snapshot))

    def get_stream_status(self) -> Dict[str, Any]:
        with self._lock:
            return self._build_stream_status_locked()

    async def wait_for_snapshot(self, timeout_seconds: float = 1.0) -> Optional[Dict[str, Any]]:
        return await asyncio.to_thread(self._wait_for_snapshot_sync, timeout_seconds)

    async def run_once_for_test(self) -> None:
        try:
            async for tick in self.provider.connect():
                self.handle_tick(tick)
                break
        except Exception as exc:
            reason, delay = self._record_connection_failure(exc)
            logger.debug(
                "[CryptoRealtimeService] websocket degraded (%s), retry in %.1fs",
                reason,
                delay,
            )

    async def _run_forever(self) -> None:
        while not self._stop_event.is_set():
            try:
                async for tick in self.provider.connect():
                    if self._stop_event.is_set():
                        break
                    self.handle_tick(tick)
            except Exception as exc:
                reason, delay = self._record_connection_failure(exc)
                log_level = logging.WARNING if self._failure_count == 1 else logging.DEBUG
                logger.log(
                    log_level,
                    "[CryptoRealtimeService] websocket degraded (%s), retry in %.1fs",
                    reason,
                    delay,
                )
                await asyncio.sleep(delay)

    def _run_background_loop(self) -> None:
        try:
            asyncio.run(self._run_forever())
        except Exception as exc:
            logger.warning("[CryptoRealtimeService] background loop stopped: %s", exc)

    def _wait_for_snapshot_sync(self, timeout_seconds: float) -> Optional[Dict[str, Any]]:
        with self._condition:
            if not self._last_snapshot:
                self._condition.wait(timeout_seconds)
            if not self._last_snapshot:
                return None
            return self._snapshot_with_freshness_locked(dict(self._last_snapshot))

    def _next_sparkline(self, symbol: str, price: float) -> list[float]:
        previous = self._ticks.get(symbol, {})
        history = previous.get("sparkline") or previous.get("trend") or []
        values = [float(value) for value in history[-23:] if _clean_number(value) is not None]
        values.append(round(price, 2))
        return values

    def _build_snapshot_locked(self) -> Dict[str, Any]:
        updated_at = _now_iso()
        items = [self._ticks[symbol] for symbol in ("BTC", "ETH", "BNB") if symbol in self._ticks]
        as_of = max((item.get("asOf") for item in items), default=updated_at)
        return {
            "source": "binance_ws",
            "sourceLabel": "Binance WS",
            "freshness": "live",
            "updatedAt": updated_at,
            "last_update": updated_at,
            "asOf": as_of,
            "isFallback": False,
            "fallback_used": False,
            "fallbackUsed": False,
            "items": items,
            "error": None,
        }

    def _snapshot_with_freshness_locked(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        current = _now()
        as_of = _parse_time(snapshot.get("asOf") or snapshot.get("updatedAt")) or current
        age_seconds = max(0.0, (current - as_of).total_seconds())
        freshness = "live" if age_seconds <= self.stale_after_seconds else "stale"
        snapshot["freshness"] = freshness
        snapshot["isStale"] = freshness == "stale"
        if freshness == "stale":
            snapshot["warning"] = "实时连接断开，显示最近快照"
        snapshot["items"] = [
            {
                **item,
                "freshness": freshness,
                "isStale": freshness == "stale",
                "warning": "实时连接断开，显示最近快照" if freshness == "stale" else item.get("warning"),
            }
            for item in snapshot.get("items", [])
        ]
        return snapshot

    def _build_stream_status_locked(self) -> Dict[str, Any]:
        return {
            "state": self._stream_state,
            "reason": self._stream_reason,
            "warning": self._stream_warning,
            "failureCount": self._failure_count,
            "nextRetryAt": self._next_retry_at.isoformat(timespec="seconds") if self._next_retry_at else None,
        }

    def _mark_stream_live_locked(self) -> None:
        self._stream_state = "live"
        self._stream_reason = None
        self._stream_warning = None
        self._failure_count = 0
        self._next_retry_at = None

    def _record_connection_failure(self, exc: Exception) -> tuple[str, float]:
        reason = self._classify_connection_failure(exc)
        warning = self._warning_for_reason(reason)
        with self._condition:
            self._failure_count += 1
            delay = self._next_reconnect_delay(self._failure_count)
            self._stream_state = "degraded"
            self._stream_reason = reason
            self._stream_warning = warning
            self._next_retry_at = _now() + timedelta(seconds=delay)
            self._condition.notify_all()
        return reason, delay

    def _next_reconnect_delay(self, failure_count: int) -> float:
        if failure_count <= 1:
            return self.reconnect_delay_seconds
        delay = self.reconnect_delay_seconds
        for _ in range(failure_count - 1):
            delay = min(self.max_reconnect_delay_seconds, delay * 2)
            if delay >= self.max_reconnect_delay_seconds:
                return self.max_reconnect_delay_seconds
        return delay

    def _classify_connection_failure(self, exc: Exception) -> str:
        message = " ".join(str(part) for part in getattr(exc, "args", ()) if part) or str(exc)
        lowered = message.lower()
        if "http 451" in lowered or "http status 451" in lowered:
            return "http_451_blocked"
        if (
            "connect call failed" in lowered
            or "connection refused" in lowered
            or "proxy" in lowered
            or "127.0.0.1" in lowered
        ):
            return "proxy_connect_failed"
        return "connection_failed"

    def _warning_for_reason(self, reason: str) -> str:
        if reason == "http_451_blocked":
            return "实时连接受限，已进入退避重试"
        if reason == "proxy_connect_failed":
            return "实时连接不可用，正在退避重试"
        return "实时连接暂不可用，正在退避重试"


_service: Optional[CryptoRealtimeService] = None
_service_lock = threading.RLock()


def should_auto_start_crypto_realtime() -> bool:
    if os.environ.get("CRYPTO_REALTIME_ENABLED", "1").lower() in {"0", "false", "no", "off"}:
        return False
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    return True


def get_crypto_realtime_service(*, auto_start: Optional[bool] = None) -> CryptoRealtimeService:
    global _service
    with _service_lock:
        if _service is None:
            _service = CryptoRealtimeService(auto_start=should_auto_start_crypto_realtime() if auto_start is None else auto_start)
        return _service
