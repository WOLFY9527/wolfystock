"""Explicit ownership for the runtime resources used by FastAPI."""

from __future__ import annotations

from contextlib import ExitStack
from typing import Callable

from src.services.crypto_realtime_service import (
    CryptoRealtimeService,
    get_crypto_realtime_service,
    should_auto_start_crypto_realtime,
)
from src.services.system_config_service import SystemConfigService
from src.services.task_queue import AnalysisTaskQueue, get_task_queue


class RuntimeContainer:
    """Own the narrow set of long-lived resources used by the API lifespan."""

    def __init__(
        self,
        *,
        system_config_service_factory: Callable[[], SystemConfigService] = SystemConfigService,
        task_queue_factory: Callable[[], AnalysisTaskQueue] = get_task_queue,
        crypto_realtime_service_factory: Callable[..., CryptoRealtimeService] = get_crypto_realtime_service,
        should_start_crypto_realtime: Callable[[], bool] = should_auto_start_crypto_realtime,
    ) -> None:
        self._system_config_service_factory = system_config_service_factory
        self._task_queue_factory = task_queue_factory
        self._crypto_realtime_service_factory = crypto_realtime_service_factory
        self._should_start_crypto_realtime = should_start_crypto_realtime
        self._system_config_service: SystemConfigService | None = None
        self._task_queue: AnalysisTaskQueue | None = None
        self._crypto_realtime_service: CryptoRealtimeService | None = None
        self._close_stack = ExitStack()
        self._started = False
        self._closed = False

    @property
    def is_started(self) -> bool:
        return self._started

    @property
    def system_config_service(self) -> SystemConfigService:
        if not self._started or self._system_config_service is None:
            raise RuntimeError("RuntimeContainer is not started")
        return self._system_config_service

    @property
    def task_queue(self) -> AnalysisTaskQueue:
        if not self._started or self._task_queue is None:
            raise RuntimeError("RuntimeContainer is not started")
        return self._task_queue

    @property
    def crypto_realtime_service(self) -> CryptoRealtimeService | None:
        if not self._started:
            raise RuntimeError("RuntimeContainer is not started")
        return self._crypto_realtime_service

    def start(self) -> None:
        """Construct resources in the existing FastAPI startup order."""
        if self._started:
            raise RuntimeError("RuntimeContainer is already started")
        if self._closed:
            raise RuntimeError("RuntimeContainer is closed")

        completed = False
        try:
            with ExitStack() as rollback:
                system_config_service = self._system_config_service_factory()
                task_queue = self._task_queue_factory()
                rollback.callback(
                    task_queue.shutdown,
                    wait=False,
                    cancel_futures=True,
                )

                crypto_realtime_service = None
                if self._should_start_crypto_realtime():
                    crypto_realtime_service = self._crypto_realtime_service_factory(
                        auto_start=True
                    )
                    rollback.callback(crypto_realtime_service.stop)

                self._system_config_service = system_config_service
                self._task_queue = task_queue
                self._crypto_realtime_service = crypto_realtime_service
                self._close_stack = rollback.pop_all()
                self._started = True
                completed = True
        finally:
            if not completed:
                self._closed = True

    def close(self) -> None:
        """Close owned resources in reverse order, at most once."""
        if self._closed:
            return

        self._closed = True
        self._started = False
        try:
            self._close_stack.close()
        finally:
            self._system_config_service = None
            self._task_queue = None
            self._crypto_realtime_service = None
