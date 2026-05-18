# -*- coding: utf-8 -*-
"""Raw yfinance transport helpers for Market Overview."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from threading import BoundedSemaphore
from typing import Any, Callable

import yfinance as yf


YFINANCE_HISTORY_TIMEOUT_SECONDS = 1.5
YFINANCE_HISTORY_TIMEOUT_WORKERS = 4

_YFINANCE_HISTORY_EXECUTOR = ThreadPoolExecutor(
    max_workers=YFINANCE_HISTORY_TIMEOUT_WORKERS,
    thread_name_prefix="market-yfinance-history",
)
_YFINANCE_HISTORY_SLOTS = BoundedSemaphore(YFINANCE_HISTORY_TIMEOUT_WORKERS)


def fetch_yfinance_quote_history_frame(ticker: str, *, timeout: float = YFINANCE_HISTORY_TIMEOUT_SECONDS) -> Any:
    return _run_yfinance_history_with_timeout(
        lambda: yf.Ticker(ticker).history(period="5d", interval="1d", auto_adjust=False),
        timeout=timeout,
        task_name="yfinance history",
    )


def fetch_yfinance_spy_atr_history_frame(*, timeout: float = YFINANCE_HISTORY_TIMEOUT_SECONDS) -> Any:
    return _run_yfinance_history_with_timeout(
        lambda: yf.Ticker("SPY").history(period="1mo", interval="1d", auto_adjust=False),
        timeout=timeout,
        task_name="yfinance history",
    )


def _run_yfinance_history_with_timeout(call: Callable[[], Any], *, timeout: float, task_name: str) -> Any:
    timeout_seconds = max(0.0, float(timeout))
    if timeout_seconds <= 0:
        raise TimeoutError(f"{task_name} timeout")
    if not _YFINANCE_HISTORY_SLOTS.acquire(blocking=False):
        raise TimeoutError(f"{task_name} timeout worker pool exhausted")

    released = False

    def release_slot(_: Any = None) -> None:
        nonlocal released
        if not released:
            released = True
            _YFINANCE_HISTORY_SLOTS.release()

    try:
        future = _YFINANCE_HISTORY_EXECUTOR.submit(call)
    except Exception:
        release_slot()
        raise

    try:
        return future.result(timeout=timeout_seconds)
    except FutureTimeoutError as exc:
        future.cancel()
        raise TimeoutError(f"{task_name} timeout after {timeout_seconds:.3f}s") from exc
    finally:
        if future.done():
            release_slot()
        else:
            future.add_done_callback(release_slot)
