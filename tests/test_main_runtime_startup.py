from __future__ import annotations

import threading
import time
import sys
from types import SimpleNamespace

import main as runtime_main
import pytest
from src.runtime.settings import SettingSource


class _FakeUvicornConfig:
    def __init__(self, app: str, **kwargs: object) -> None:
        self.app = app
        self.kwargs = kwargs


class _ControllableServer:
    instances: list["_ControllableServer"] = []
    allow_start = threading.Event()

    def __init__(self, config: _FakeUvicornConfig) -> None:
        self.config = config
        self.started = False
        self.should_exit = False
        self.__class__.instances.append(self)

    def run(self) -> None:
        self.__class__.allow_start.wait(timeout=1)
        self.started = True
        while not self.should_exit:
            time.sleep(0.001)


class _FailingServer:
    failure: BaseException | None = None

    def __init__(self, config: _FakeUvicornConfig) -> None:
        self.config = config
        self.started = False
        self.should_exit = False

    def run(self) -> None:
        if self.failure is not None:
            raise self.failure


class _NeverStartingServer:
    instances: list["_NeverStartingServer"] = []

    def __init__(self, config: _FakeUvicornConfig) -> None:
        self.config = config
        self.started = False
        self.should_exit = False
        self.__class__.instances.append(self)

    def run(self) -> None:
        while not self.should_exit:
            time.sleep(0.001)


class _RecordingHandle:
    def __init__(self) -> None:
        self.stop_calls = 0

    def stop_and_join(self, timeout: float = 10.0) -> bool:
        self.stop_calls += 1
        return True


class _ReturningScheduler:
    def __init__(self, schedule_time: str) -> None:
        self.schedule_time = schedule_time

    def add_daily_task(self, **kwargs: object) -> None:
        return None

    def run(self) -> None:
        return None


def _args(**overrides: object) -> SimpleNamespace:
    values = {
        "debug": False,
        "stocks": None,
        "serve": False,
        "serve_only": False,
        "host": "127.0.0.1",
        "port": 8123,
        "backtest": False,
        "backtest_code": None,
        "backtest_force": False,
        "backtest_days": None,
        "market_review": False,
        "scanner": False,
        "scanner_schedule": False,
        "schedule": False,
        "no_run_immediately": True,
        "force_run": False,
        "no_notify": True,
        "no_market_review": True,
        "dry_run": True,
        "single_notify": False,
        "workers": None,
        "no_context_snapshot": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _config(**overrides: object) -> SimpleNamespace:
    values = {
        "log_dir": None,
        "log_level": "INFO",
        "webui_host": "127.0.0.1",
        "webui_port": 8765,
        "webui_enabled": False,
        "dingtalk_stream_enabled": False,
        "feishu_stream_enabled": False,
        "schedule_enabled": False,
        "scanner_schedule_enabled": False,
        "watchlist_score_refresh_enabled": False,
        "schedule_time": "09:00",
        "schedule_run_immediately": False,
        "run_immediately": False,
        "validate": lambda: [],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _patch_main(
    monkeypatch,
    *,
    args: SimpleNamespace,
    config: SimpleNamespace | None = None,
) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setattr(runtime_main, "parse_arguments", lambda: args)
    monkeypatch.setattr(runtime_main, "get_config", lambda: config or _config())
    monkeypatch.setattr(runtime_main, "setup_logging", lambda **kwargs: None)
    monkeypatch.setattr(runtime_main, "prepare_webui_frontend_assets", lambda: True)


def test_start_api_server_waits_for_server_started(monkeypatch, caplog) -> None:
    caplog.set_level("INFO", logger="main")
    _ControllableServer.instances.clear()
    _ControllableServer.allow_start.clear()
    monkeypatch.setattr("uvicorn.Config", _FakeUvicornConfig)
    monkeypatch.setattr("uvicorn.Server", _ControllableServer)
    timer = threading.Timer(0.03, _ControllableServer.allow_start.set)
    timer.start()

    try:
        handle = runtime_main.start_api_server(
            host="127.0.0.1",
            port=8123,
            config=SimpleNamespace(log_level="INFO"),
            startup_timeout=0.5,
        )
    finally:
        timer.cancel()

    server = _ControllableServer.instances[0]
    assert handle.server is server
    assert handle.state.value == "ready"
    assert server.config.app == "api.app:app"
    assert server.config.kwargs["host"] == "127.0.0.1"
    assert server.config.kwargs["port"] == 8123
    messages = [record.getMessage() for record in caplog.records]
    starting_index = next(index for index, message in enumerate(messages) if "正在启动" in message)
    started_index = next(index for index, message in enumerate(messages) if "已启动" in message)
    assert starting_index < started_index

    assert handle.stop_and_join(timeout=0.5) is True
    assert handle.state.value == "stopped"
    assert not handle.thread.is_alive()


@pytest.mark.parametrize(
    ("failure", "failure_type"),
    [
        (ImportError("private import detail"), "ImportError"),
        (RuntimeError("private lifespan detail"), "RuntimeError"),
        (OSError("private bind detail"), "OSError"),
        (SystemExit(3), "SystemExit"),
    ],
    ids=["import", "lifespan", "bind", "system-exit"],
)
def test_start_api_server_normalizes_runner_failure(
    monkeypatch, failure: BaseException, failure_type: str
) -> None:
    _FailingServer.failure = failure
    monkeypatch.setattr("uvicorn.Config", _FakeUvicornConfig)
    monkeypatch.setattr("uvicorn.Server", _FailingServer)

    with pytest.raises(runtime_main.ApiStartupError) as exc_info:
        runtime_main.start_api_server(
            "127.0.0.1",
            8123,
            SimpleNamespace(log_level="INFO"),
            startup_timeout=0.5,
        )

    assert exc_info.value.reason == "runner_exited_before_start"
    assert exc_info.value.failure_type == failure_type
    assert "private" not in str(exc_info.value)


def test_start_api_server_rejects_pre_start_normal_exit(monkeypatch) -> None:
    _FailingServer.failure = None
    monkeypatch.setattr("uvicorn.Config", _FakeUvicornConfig)
    monkeypatch.setattr("uvicorn.Server", _FailingServer)

    with pytest.raises(runtime_main.ApiStartupError) as exc_info:
        runtime_main.start_api_server(
            "127.0.0.1",
            8123,
            SimpleNamespace(log_level="INFO"),
            startup_timeout=0.5,
        )

    assert exc_info.value.reason == "runner_exited_before_start"
    assert exc_info.value.failure_type == "none"


def test_start_api_server_normalizes_thread_start_failure(monkeypatch) -> None:
    monkeypatch.setattr("uvicorn.Config", _FakeUvicornConfig)
    monkeypatch.setattr("uvicorn.Server", _NeverStartingServer)
    monkeypatch.setattr(
        runtime_main.threading.Thread,
        "start",
        lambda self: (_ for _ in ()).throw(OSError("private thread detail")),
    )

    with pytest.raises(runtime_main.ApiStartupError) as exc_info:
        runtime_main.start_api_server(
            "127.0.0.1",
            8123,
            SimpleNamespace(log_level="INFO"),
            startup_timeout=0.5,
        )

    assert exc_info.value.reason == "thread_start_failed"
    assert exc_info.value.failure_type == "OSError"
    assert "private" not in str(exc_info.value)


def test_api_handle_observes_unexpected_exit_after_ready(monkeypatch) -> None:
    class StartThenExitServer:
        exit_runner = threading.Event()

        def __init__(self, config: _FakeUvicornConfig) -> None:
            self.config = config
            self.started = False
            self.should_exit = False

        def run(self) -> None:
            self.started = True
            self.exit_runner.wait(timeout=1)

    StartThenExitServer.exit_runner.clear()
    monkeypatch.setattr("uvicorn.Config", _FakeUvicornConfig)
    monkeypatch.setattr("uvicorn.Server", StartThenExitServer)
    handle = runtime_main.start_api_server(
        "127.0.0.1",
        8123,
        SimpleNamespace(log_level="INFO"),
        startup_timeout=0.5,
    )

    StartThenExitServer.exit_runner.set()
    handle.thread.join(timeout=0.5)

    assert not handle.thread.is_alive()
    assert handle.state is runtime_main.ApiServerState.UNEXPECTED_EXIT


def test_start_api_server_timeout_stops_and_joins_runner(monkeypatch) -> None:
    _NeverStartingServer.instances.clear()
    monkeypatch.setattr("uvicorn.Config", _FakeUvicornConfig)
    monkeypatch.setattr("uvicorn.Server", _NeverStartingServer)

    with pytest.raises(runtime_main.ApiStartupError) as exc_info:
        runtime_main.start_api_server(
            "127.0.0.1",
            8123,
            SimpleNamespace(log_level="INFO"),
            startup_timeout=0.02,
        )

    server = _NeverStartingServer.instances[0]
    assert exc_info.value.reason == "startup_timeout"
    assert server.should_exit is True


def test_startup_handshake_does_not_require_application_readiness(monkeypatch) -> None:
    class NotReadyServer(_ControllableServer):
        readiness_status = 503

    NotReadyServer.instances.clear()
    NotReadyServer.allow_start.set()
    monkeypatch.setattr("uvicorn.Config", _FakeUvicornConfig)
    monkeypatch.setattr("uvicorn.Server", NotReadyServer)

    handle = runtime_main.start_api_server(
        "127.0.0.1",
        8123,
        SimpleNamespace(log_level="INFO"),
        startup_timeout=0.5,
    )

    assert handle.state is runtime_main.ApiServerState.READY
    assert handle.server.readiness_status == 503
    assert handle.stop_and_join(timeout=0.5) is True


@pytest.mark.parametrize(
    "args",
    [
        _args(serve_only=True),
        _args(serve=True),
        _args(serve=True, schedule=True),
    ],
    ids=["serve-only", "serve", "scheduler"],
)
def test_main_returns_one_and_skips_bots_on_api_startup_failure(monkeypatch, args) -> None:
    _patch_main(monkeypatch, args=args)
    bot_calls: list[str] = []
    monkeypatch.setattr(
        runtime_main,
        "start_api_server",
        lambda **kwargs: (_ for _ in ()).throw(
            runtime_main.ApiStartupError("runner_exited_before_start", "SystemExit")
        ),
    )
    monkeypatch.setattr(runtime_main, "start_bot_stream_clients", lambda config: bot_calls.append("bot"))
    monkeypatch.setattr(runtime_main.time, "sleep", lambda seconds: (_ for _ in ()).throw(KeyboardInterrupt()))
    monkeypatch.setattr("src.scheduler.Scheduler", _ReturningScheduler)

    assert runtime_main.main() == 1
    assert bot_calls == []


def test_static_asset_degradation_remains_nonfatal(monkeypatch) -> None:
    args = _args(serve_only=True, host="0.0.0.0", port=8000)
    config = _config(
        webui_host="127.0.0.1",
        webui_port=8765,
        runtime_settings=SimpleNamespace(
            provenance={
                "WEBUI_HOST": SimpleNamespace(source=SettingSource.ENV_FILE),
                "WEBUI_PORT": SimpleNamespace(source=SettingSource.ENV_FILE),
            }
        ),
    )
    _patch_main(monkeypatch, args=args, config=config)
    handle = _RecordingHandle()
    bot_calls: list[str] = []
    server_kwargs: dict[str, object] = {}
    monkeypatch.setattr(runtime_main, "prepare_webui_frontend_assets", lambda: False)
    monkeypatch.setattr(
        runtime_main,
        "start_api_server",
        lambda **kwargs: (server_kwargs.update(kwargs) or handle),
    )
    monkeypatch.setattr(runtime_main, "start_bot_stream_clients", lambda config: bot_calls.append("bot"))
    monkeypatch.setattr(runtime_main.time, "sleep", lambda seconds: (_ for _ in ()).throw(KeyboardInterrupt()))

    assert runtime_main.main() == 0
    assert bot_calls == ["bot"]
    assert handle.stop_calls == 1
    assert server_kwargs["host"] == "127.0.0.1"
    assert server_kwargs["port"] == 8765


def test_main_stops_api_when_interrupted_during_bot_start(monkeypatch) -> None:
    _patch_main(monkeypatch, args=_args(serve=True))
    handle = _RecordingHandle()
    monkeypatch.setattr(runtime_main, "start_api_server", lambda **kwargs: handle)
    monkeypatch.setattr(
        runtime_main,
        "start_bot_stream_clients",
        lambda config: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    assert runtime_main.main() == 130
    assert handle.stop_calls == 1


@pytest.mark.parametrize(
    "args",
    [
        _args(serve=True),
        _args(serve=True, schedule=True),
        _args(serve=True, backtest=True),
    ],
    ids=["serve", "scheduler", "one-shot"],
)
def test_main_stops_api_once_on_every_successful_exit(monkeypatch, args) -> None:
    _patch_main(monkeypatch, args=args)
    handle = _RecordingHandle()
    monkeypatch.setattr(runtime_main, "start_api_server", lambda **kwargs: handle)
    monkeypatch.setattr(runtime_main, "start_bot_stream_clients", lambda config: None)
    monkeypatch.setattr(runtime_main.time, "sleep", lambda seconds: (_ for _ in ()).throw(KeyboardInterrupt()))
    monkeypatch.setattr("src.scheduler.Scheduler", _ReturningScheduler)

    class BacktestService:
        def run_backtest(self, **kwargs: object) -> dict[str, int]:
            return {"processed": 0, "saved": 0, "completed": 0, "insufficient": 0, "errors": 0}

    monkeypatch.setitem(
        sys.modules,
        "src.services.backtest_service",
        SimpleNamespace(BacktestService=BacktestService),
    )

    assert runtime_main.main() == 0
    assert handle.stop_calls == 1


def test_serve_only_fails_closed_when_api_start_is_suppressed(monkeypatch) -> None:
    _patch_main(monkeypatch, args=_args(serve_only=True))
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setattr(runtime_main.time, "sleep", lambda seconds: (_ for _ in ()).throw(KeyboardInterrupt()))

    assert runtime_main.main() == 1
