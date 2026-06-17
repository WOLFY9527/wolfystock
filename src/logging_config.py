# -*- coding: utf-8 -*-
"""
===================================
日志配置模块 - 统一的日志系统初始化
===================================

职责：
1. 提供统一的日志格式和配置常量
2. 支持控制台 + 文件（常规/调试）三层日志输出
3. 自动降低第三方库日志级别
"""

import logging
import re
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, List, Optional


LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(pathname)s:%(lineno)d | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
REDACTED_TEXT = "<redacted>"

_SENSITIVE_KEY_FRAGMENTS = (
    "authorization",
    "cookie",
    "setcookie",
    "token",
    "sessionid",
    "password",
    "passwd",
    "apikey",
    "secret",
    "credential",
    "privatekey",
)

_SENSITIVE_TEXT_PATTERNS = (
    re.compile(r"(?i)\b(authorization)\s*[:=]\s*(?:bearer\s+)?[^\s,;]+"),
    re.compile(r"(?i)\b(cookie|set-cookie)\s*[:=]\s*[^\n]+"),
    re.compile(
        r"(?i)\b([a-z0-9_-]*(?:api[_-]?key|token|secret|password|session[_-]?id)[a-z0-9_-]*)\s*[:=]\s*[^,\s;]+"
    ),
    re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/-]+=*"),
)


class RelativePathFormatter(logging.Formatter):
    """自定义 Formatter，输出相对路径而非绝对路径"""

    def __init__(self, fmt=None, datefmt=None, relative_to=None):
        super().__init__(fmt, datefmt)
        self.relative_to = Path(relative_to) if relative_to else Path.cwd()

    def format(self, record):
        # 将绝对路径转为相对路径
        try:
            record.pathname = str(Path(record.pathname).relative_to(self.relative_to))
        except ValueError:
            # 如果无法转换为相对路径，保持原样
            pass
        return super().format(record)


class RedactingRelativePathFormatter(RelativePathFormatter):
    """Formatter that strips credential-like values before rendering records."""

    def format(self, record):
        original_msg = record.msg
        original_args = record.args
        try:
            record.msg = redact_log_metadata(record.msg)
            record.args = redact_log_metadata(record.args) if record.args else record.args
            return super().format(record)
        finally:
            record.msg = original_msg
            record.args = original_args

    def formatException(self, exc_info):
        return _redact_text(super().formatException(exc_info))


def _normalized_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _is_sensitive_key(value: Any) -> bool:
    normalized = _normalized_key(value)
    return any(fragment in normalized for fragment in _SENSITIVE_KEY_FRAGMENTS)


def _redact_text(value: str) -> str:
    text = str(value)
    for pattern in _SENSITIVE_TEXT_PATTERNS:
        text = pattern.sub(lambda match: f"{match.group(1) if match.groups() else 'value'}: {REDACTED_TEXT}", text)
    return text


def redact_log_metadata(value: Any) -> Any:
    """Return a copy with credential-bearing keys and obvious inline tokens redacted."""
    if isinstance(value, dict):
        return {
            key: REDACTED_TEXT if _is_sensitive_key(key) else redact_log_metadata(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_log_metadata(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_log_metadata(item) for item in value)
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _today_string(today: Optional[str] = None) -> str:
    if today:
        return str(today)
    return datetime.now().strftime("%Y%m%d")


def _runtime_log_path(log_prefix: str, log_dir: str, today: Optional[str] = None) -> Path:
    return Path(log_dir) / f"{log_prefix}_{_today_string(today)}.log"


def _find_file_handler(target: Path) -> Optional[logging.FileHandler]:
    target_resolved = target.resolve()
    for handler in logging.getLogger().handlers:
        if not isinstance(handler, logging.FileHandler):
            continue
        try:
            handler_path = Path(str(handler.baseFilename)).resolve()
        except Exception:
            continue
        if handler_path == target_resolved:
            return handler
    return None


def describe_runtime_file_logging(
    log_prefix: str = "api_server",
    log_dir: str = "./logs",
    today: Optional[str] = None,
) -> dict[str, Any]:
    """Describe the current dated runtime file sink without reading log contents."""
    target = _runtime_log_path(log_prefix, log_dir, today)
    attached = _find_file_handler(target) is not None
    exists = target.exists()
    status = "active" if attached else "file_present_not_attached" if exists else "missing"
    reason_code = None
    if status == "file_present_not_attached":
        reason_code = "runtime_file_handler_missing"
    elif status == "missing":
        reason_code = "runtime_log_file_missing"
    return {
        "enabled": True,
        "status": status,
        "logPrefix": log_prefix,
        "logDir": str(target.parent),
        "path": str(target),
        "fileName": target.name,
        "date": _today_string(today),
        "alreadyConfigured": attached,
        "fileExists": exists,
        "reasonCode": reason_code,
    }


def ensure_runtime_file_logging(
    log_prefix: str = "api_server",
    log_dir: str = "./logs",
    level: int = logging.INFO,
    today: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    extra_quiet_loggers: Optional[List[str]] = None,
) -> dict[str, Any]:
    """Attach a dated file handler idempotently without replacing existing handlers."""
    target = _runtime_log_path(log_prefix, log_dir, today)
    target.parent.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger()
    if root_logger.level == logging.NOTSET or root_logger.level > logging.DEBUG:
        root_logger.setLevel(logging.DEBUG)

    existing_handler = _find_file_handler(target)
    if existing_handler is None:
        project_root = Path.cwd()
        handler = RotatingFileHandler(
            target,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        handler.setLevel(level)
        handler.setFormatter(RedactingRelativePathFormatter(LOG_FORMAT, LOG_DATE_FORMAT, relative_to=project_root))
        root_logger.addHandler(handler)

    quiet_loggers = DEFAULT_QUIET_LOGGERS.copy()
    if extra_quiet_loggers:
        quiet_loggers.extend(extra_quiet_loggers)
    for logger_name in quiet_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    result = describe_runtime_file_logging(log_prefix=log_prefix, log_dir=log_dir, today=today)
    result["alreadyConfigured"] = existing_handler is not None
    return result



# 默认需要降低日志级别的第三方库
DEFAULT_QUIET_LOGGERS = [
    'urllib3',
    'sqlalchemy',
    'google',
    'httpx',
]


def setup_logging(
    log_prefix: str = "app",
    log_dir: str = "./logs",
    console_level: Optional[int] = None,
    debug: bool = False,
    extra_quiet_loggers: Optional[List[str]] = None,
) -> None:
    """
    统一的日志系统初始化

    配置三层日志输出：
    1. 控制台：根据 debug 参数或 console_level 设置级别
    2. 常规日志文件：INFO 级别，10MB 轮转，保留 5 个备份
    3. 调试日志文件：DEBUG 级别，50MB 轮转，保留 3 个备份

    Args:
        log_prefix: 日志文件名前缀（如 "api_server" -> api_server_20240101.log）
        log_dir: 日志文件目录，默认 ./logs
        console_level: 控制台日志级别（可选，优先于 debug 参数）
        debug: 是否启用调试模式（控制台输出 DEBUG 级别）
        extra_quiet_loggers: 额外需要降低日志级别的第三方库列表
    """
    # 确定控制台日志级别
    if console_level is not None:
        level = console_level
    else:
        level = logging.DEBUG if debug else logging.INFO

    # 创建日志目录
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # 日志文件路径（按日期分文件）
    today_str = datetime.now().strftime('%Y%m%d')
    log_file = log_path / f"{log_prefix}_{today_str}.log"
    debug_log_file = log_path / f"{log_prefix}_debug_{today_str}.log"

    # 配置根 logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # 根 logger 设为 DEBUG，由 handler 控制输出级别

    # 清除已有 handler，避免重复添加
    if root_logger.handlers:
        root_logger.handlers.clear()
    # 创建相对路径 Formatter（相对于项目根目录）
    project_root = Path.cwd()
    rel_formatter = RelativePathFormatter(
        LOG_FORMAT, LOG_DATE_FORMAT, relative_to=project_root
    )
    # Handler 1: 控制台输出
    # Windows 中文控制台常见 cp936/gbk 编码下，emoji 等字符可能触发 UnicodeEncodeError。
    # 这里采用 errors=replace，避免日志写入异常影响业务流程。
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(errors="replace")
        except Exception:
            pass
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(rel_formatter)
    root_logger.addHandler(console_handler)

    # Handler 2: 常规日志文件（INFO 级别，10MB 轮转）
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(rel_formatter)
    root_logger.addHandler(file_handler)

    # Handler 3: 调试日志文件（DEBUG 级别，包含所有详细信息）
    debug_handler = RotatingFileHandler(
        debug_log_file,
        maxBytes=50 * 1024 * 1024,  # 50MB
        backupCount=3,
        encoding='utf-8'
    )
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(rel_formatter)
    root_logger.addHandler(debug_handler)

    # 降低第三方库的日志级别
    quiet_loggers = DEFAULT_QUIET_LOGGERS.copy()
    if extra_quiet_loggers:
        quiet_loggers.extend(extra_quiet_loggers)

    for logger_name in quiet_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    # 输出初始化完成信息（使用相对路径）
    try:
        rel_log_path = log_path.resolve().relative_to(project_root)
    except ValueError:
        rel_log_path = log_path

    try:
        rel_log_file = log_file.resolve().relative_to(project_root)
    except ValueError:
        rel_log_file = log_file

    try:
        rel_debug_log_file = debug_log_file.resolve().relative_to(project_root)
    except ValueError:
        rel_debug_log_file = debug_log_file

    logging.info(f"日志系统初始化完成，日志目录: {rel_log_path}")
    logging.info(f"常规日志: {rel_log_file}")
    logging.info(f"调试日志: {rel_debug_log_file}")
