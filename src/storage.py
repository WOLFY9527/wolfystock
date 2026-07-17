# -*- coding: utf-8 -*-
"""
===================================
A股自选股智能分析系统 - 存储层
===================================

职责：
1. 管理 SQLite 数据库连接（单例模式）
2. 定义 ORM 数据模型
3. 提供数据存取接口
4. 实现智能更新逻辑（断点续传）
"""

import atexit
from contextlib import contextmanager
import hashlib
import json
import logging
import re
from datetime import datetime, date, timedelta, time
from types import SimpleNamespace
from typing import Optional, List, Dict, Any, TYPE_CHECKING, Tuple, Iterable
from urllib.parse import unquote_plus, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import (
    create_engine,
    Column,
    String,
    Float,
    Boolean,
    Date,
    DateTime,
    Integer,
    Numeric,
    ForeignKey,
    Index,
    UniqueConstraint,
    Text,
    select,
    update,
    and_,
    or_,
    delete,
    desc,
    asc,
    func,
    inspect,
)
from sqlalchemy.orm import (
    declarative_base,
    sessionmaker,
    Session,
)
from sqlalchemy.exc import IntegrityError

from src.config import get_config
from src.core.trading_calendar import MARKET_TIMEZONE, get_market_for_stock
from src.utils.security import is_sensitive_key, sanitize_message, sanitize_metadata
from src.multi_user import (
    BOOTSTRAP_ADMIN_DISPLAY_NAME,
    BOOTSTRAP_ADMIN_USER_ID,
    BOOTSTRAP_ADMIN_USERNAME,
    OWNERSHIP_SCOPE_SYSTEM,
    OWNERSHIP_SCOPE_USER,
    ROLE_ADMIN,
    ROLE_USER,
    normalize_role,
    normalize_scope,
)
from src.admin_rbac import ADMIN_RBAC_ROLE_CAPABILITIES, ADMIN_RBAC_ROLES
from src.services.us_history_helper import LOCAL_US_PARQUET_SOURCE
from src.postgres_identity_store import PostgresPhaseAStore
from src.postgres_analysis_chat_store import PostgresPhaseBStore
from src.postgres_market_metadata_store import PostgresPhaseCStore
from src.postgres_scanner_watchlist_store import PostgresPhaseDStore
from src.postgres_backtest_store import PostgresPhaseEStore
from src.postgres_portfolio_coexistence_store import PostgresPhaseFStore, phase_f_ledger_shadow_id
from src.postgres_control_plane_store import PostgresPhaseGStore
import src.storage_phase_g_observability as storage_phase_g_observability
import src.storage_postgres_bridge as storage_postgres_bridge
import src.storage_topology_report as storage_topology_report
from src.utils.time_utils import to_beijing_iso8601

logger = logging.getLogger(__name__)
AdminNotificationService = None
DEFAULT_RECENT_ANALYSIS_SYMBOL_LIMIT = 100
MAX_RECENT_ANALYSIS_SYMBOL_LIMIT = 500
_DB_URL_REDACTED_VALUE = "***"


def _redact_db_url_query_for_log(query: str) -> str:
    if not query:
        return query

    redacted_parts: List[str] = []
    for part in query.split("&"):
        key, separator, _value = part.partition("=")
        try:
            decoded_key = unquote_plus(key)
        except Exception:
            decoded_key = key
        if separator and is_sensitive_key(decoded_key):
            redacted_parts.append(f"{key}{separator}{_DB_URL_REDACTED_VALUE}")
        else:
            redacted_parts.append(part)
    return "&".join(redacted_parts)


def _replace_db_url_query_for_log(db_url: str, redacted_query: str) -> str:
    before_query, separator, query_and_fragment = db_url.partition("?")
    if not separator:
        return db_url

    _original_query, fragment_separator, fragment = query_and_fragment.partition("#")
    return f"{before_query}?{redacted_query}{fragment_separator}{fragment}"


def _redact_db_url_for_log(db_url: Any) -> str:
    """Return a display-only DB URL with credentials masked."""
    text = str(db_url or "")
    if not text:
        return text

    try:
        parsed = urlsplit(text)
    except ValueError:
        return sanitize_message(text)

    if not parsed.scheme:
        return sanitize_message(text)

    query = _redact_db_url_query_for_log(parsed.query)
    if not parsed.netloc:
        return sanitize_message(_replace_db_url_query_for_log(text, query))

    netloc = parsed.netloc
    if "@" in netloc:
        userinfo, hostinfo = netloc.rsplit("@", 1)
        if ":" in userinfo:
            username, _password = userinfo.split(":", 1)
            userinfo = f"{username}:{_DB_URL_REDACTED_VALUE}"
        netloc = f"{userinfo}@{hostinfo}"

    redacted = urlunsplit((parsed.scheme, netloc, parsed.path, query, parsed.fragment))
    return sanitize_message(redacted)


def _sanitize_database_topology_for_log(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: Dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if isinstance(item, str) and ("url" in key_text.lower() or is_sensitive_key(key_text)):
                sanitized[key_text] = _redact_db_url_for_log(item)
            else:
                sanitized[key_text] = _sanitize_database_topology_for_log(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_database_topology_for_log(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_database_topology_for_log(item) for item in value)
    if isinstance(value, str):
        return sanitize_message(value)
    return value


def _execution_log_level_from_status(status: Any) -> str:
    normalized = str(status or "").strip().lower()
    if normalized in {"critical", "fatal"}:
        return "CRITICAL"
    if normalized in {"failed", "error", "failed_runtime", "empty_result", "invalid_response", "insufficient_fields"}:
        return "ERROR"
    if normalized in {"warning", "partial", "partial_success", "timeout", "timed_out", "timeout_unknown", "switched_to_fallback"}:
        return "WARNING"
    if normalized in {"notice"}:
        return "NOTICE"
    return "INFO"

_POSTGRES_PHASE_STORE_SPECS = tuple(
    (
        spec.phase_key,
        spec.store_attr,
        spec.enabled_attr,
        spec.store_cls,
    )
    for spec in storage_postgres_bridge.iter_phase_store_specs()
)

# SQLAlchemy ORM 基类
Base = declarative_base()

DURABLE_TASK_ACTIVE_STATUSES = frozenset(
    {
        "queued",
        "pending",
        "waiting_retry",
        "leased",
        "processing",
        "running",
    }
)

if TYPE_CHECKING:
    from src.search_service import SearchResponse


# === 数据模型定义 ===

class StockDaily(Base):
    """
    股票日线数据模型
    
    存储每日行情数据和计算的技术指标
    支持多股票、多日期的唯一约束
    """
    __tablename__ = 'stock_daily'
    
    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 股票代码（如 600519, 000001）
    code = Column(String(10), nullable=False, index=True)
    
    # 交易日期
    date = Column(Date, nullable=False, index=True)
    
    # OHLC 数据
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    
    # 成交数据
    volume = Column(Float)  # 成交量（股）
    amount = Column(Float)  # 成交额（元）
    pct_chg = Column(Float)  # 涨跌幅（%）
    
    # 技术指标
    ma5 = Column(Float)
    ma10 = Column(Float)
    ma20 = Column(Float)
    volume_ratio = Column(Float)  # 量比
    
    # 数据来源
    data_source = Column(String(50))  # 记录数据来源（如 AkshareFetcher）
    
    # 更新时间
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 唯一约束：同一股票同一日期只能有一条数据
    __table_args__ = (
        UniqueConstraint('code', 'date', name='uix_code_date'),
        Index('ix_code_date', 'code', 'date'),
    )
    
    def __repr__(self):
        return f"<StockDaily(code={self.code}, date={self.date}, close={self.close})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'code': self.code,
            'date': self.date,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'amount': self.amount,
            'pct_chg': self.pct_chg,
            'ma5': self.ma5,
            'ma10': self.ma10,
            'ma20': self.ma20,
            'volume_ratio': self.volume_ratio,
            'data_source': self.data_source,
        }


class NewsIntel(Base):
    """
    新闻情报数据模型

    存储搜索到的新闻情报条目，用于后续分析与查询
    """
    __tablename__ = 'news_intel'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 关联用户查询操作
    query_id = Column(String(64), index=True)

    # 股票信息
    code = Column(String(10), nullable=False, index=True)
    name = Column(String(50))

    # 搜索上下文
    dimension = Column(String(32), index=True)  # latest_news / risk_check / earnings / market_analysis / industry
    query = Column(String(255))
    provider = Column(String(32), index=True)

    # 新闻内容
    title = Column(String(300), nullable=False)
    snippet = Column(Text)
    url = Column(String(1000), nullable=False)
    source = Column(String(100))
    published_date = Column(DateTime, index=True)

    # 入库时间
    fetched_at = Column(DateTime, default=datetime.now, index=True)
    query_source = Column(String(32), index=True)  # bot/web/cli/system
    requester_platform = Column(String(20))
    requester_user_id = Column(String(64))
    requester_user_name = Column(String(64))
    requester_chat_id = Column(String(64))
    requester_message_id = Column(String(64))
    requester_query = Column(String(255))

    __table_args__ = (
        UniqueConstraint('url', name='uix_news_url'),
        Index('ix_news_code_pub', 'code', 'published_date'),
    )

    def __repr__(self) -> str:
        return f"<NewsIntel(code={self.code}, title={self.title[:20]}...)>"


class FundamentalSnapshot(Base):
    """
    基本面上下文快照（P0 write-only）。

    仅用于写入，主链路不依赖读取该表，便于后续回测/画像扩展。
    """
    __tablename__ = 'fundamental_snapshot'

    id = Column(Integer, primary_key=True, autoincrement=True)
    query_id = Column(String(64), nullable=False, index=True)
    code = Column(String(10), nullable=False, index=True)
    payload = Column(Text, nullable=False)
    source_chain = Column(Text)
    coverage = Column(Text)
    created_at = Column(DateTime, default=datetime.now, index=True)

    __table_args__ = (
        Index('ix_fundamental_snapshot_query_code', 'query_id', 'code'),
        Index('ix_fundamental_snapshot_created', 'created_at'),
    )

    def __repr__(self) -> str:
        return f"<FundamentalSnapshot(query_id={self.query_id}, code={self.code})>"


class MarketOverviewSnapshot(Base):
    """Last-known-good market overview panel payload."""

    __tablename__ = 'market_overview_snapshots'

    key = Column(String(128), primary_key=True)
    payload_json = Column(Text, nullable=False)
    as_of = Column(DateTime, index=True)
    updated_at = Column(DateTime, default=datetime.now, nullable=False, index=True)
    source = Column(String(64))
    freshness = Column(String(32))
    is_fallback = Column(Boolean, nullable=False, default=False)
    error_count = Column(Integer, nullable=False, default=0)
    last_error = Column(Text)
    last_error_at = Column(DateTime)

    __table_args__ = (
        Index('ix_market_overview_snapshots_updated', 'updated_at'),
    )


class QuoteOhlcvSnapshotRow(Base):
    """Canonical quote/OHLCV snapshot lineage row owned by DatabaseManager."""

    __tablename__ = 'quote_ohlcv_snapshots'

    snapshot_id = Column(String(96), primary_key=True)
    snapshot_kind = Column(String(16), nullable=False, index=True)
    symbol = Column(String(32), nullable=False, index=True)
    market = Column(String(16), nullable=False, index=True)
    quote_as_of = Column(String(64))
    bar_trade_date_time = Column(String(64))
    retrieval_time = Column(String(64), nullable=False, index=True)
    source_id = Column(String(96), nullable=False)
    source_type = Column(String(64), nullable=False)
    authority_state = Column(String(64), nullable=False)
    display_state = Column(String(64), nullable=False)
    freshness_state = Column(String(64), nullable=False)
    coverage_state = Column(String(64), nullable=False)
    ohlcv_basis = Column(String(32))
    lineage_ref = Column(String(255), nullable=False)
    payload_json = Column(Text, nullable=False)
    payload_fingerprint = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)

    __table_args__ = (
        Index(
            'ix_quote_ohlcv_snapshots_symbol_lookup',
            'market',
            'symbol',
            'snapshot_kind',
            'retrieval_time',
        ),
        Index('ix_quote_ohlcv_snapshots_lineage_ref', 'lineage_ref'),
    )


class ScenarioBaselineSnapshotRow(Base):
    """Canonical Scenario Lab baseline snapshot row owned by DatabaseManager."""

    __tablename__ = 'scenario_baseline_snapshots'

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_type = Column(String(32), nullable=False)
    owner_value = Column(String(96), nullable=False)
    snapshot_id = Column(String(96), nullable=False)
    scope_type = Column(String(16), nullable=False)
    scope_value = Column(String(32), nullable=False)
    created_at = Column(String(64), nullable=False)
    as_of = Column(String(64), nullable=False)
    readiness_state = Column(String(32), nullable=False)
    content_hash = Column(String(96), nullable=False)
    content_version_ref = Column(String(180), nullable=False)
    payload_json = Column(Text, nullable=False)
    created_at_db = Column(DateTime, default=datetime.now, nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint(
            'owner_type',
            'owner_value',
            'snapshot_id',
            name='uix_scenario_baseline_owner_snapshot',
        ),
        Index(
            'ix_scenario_baseline_latest_scope',
            'owner_type',
            'owner_value',
            'scope_type',
            'scope_value',
            'as_of',
            'created_at',
            'snapshot_id',
        ),
    )


class AppUser(Base):
    """Persisted application user identity for the multi-user foundation."""

    __tablename__ = 'app_users'

    id = Column(String(64), primary_key=True)
    username = Column(String(128), nullable=False, unique=True, index=True)
    display_name = Column(String(128))
    password_hash = Column(String(255))
    mfa_enabled = Column(Boolean, nullable=False, default=False, index=True)
    mfa_secret_ref = Column(Text)
    mfa_recovery_codes_hash = Column(Text)
    mfa_created_at = Column(DateTime, index=True)
    mfa_enabled_at = Column(DateTime, index=True)
    mfa_last_verified_at = Column(DateTime, index=True)
    role = Column(String(16), nullable=False, default=ROLE_USER, index=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index('ix_app_user_role_active', 'role', 'is_active'),
    )


class AppUserSession(Base):
    """Persistent authenticated session record for cookie-based auth."""

    __tablename__ = 'app_user_sessions'

    session_id = Column(String(64), primary_key=True)
    user_id = Column(String(64), ForeignKey('app_users.id'), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.now, index=True)
    last_seen_at = Column(DateTime, default=datetime.now, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    revoked_at = Column(DateTime, index=True)

    __table_args__ = (
        Index('ix_app_user_session_user_expiry', 'user_id', 'expires_at'),
        Index('ix_app_user_session_user_revoked_expiry', 'user_id', 'revoked_at', 'expires_at'),
        Index('ix_app_user_session_revoked', 'revoked_at'),
    )


class AuthRateLimitBucket(Base):
    """Durable auth throttling bucket keyed by hashed source/account identifiers."""

    __tablename__ = 'auth_rate_limit_buckets'

    bucket_key = Column(String(96), primary_key=True)
    bucket_type = Column(String(16), nullable=False, index=True)
    failure_count = Column(Integer, nullable=False, default=0)
    first_failed_at = Column(DateTime, nullable=False, default=datetime.now, index=True)
    last_failed_at = Column(DateTime, nullable=False, default=datetime.now, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)

    __table_args__ = (
        Index('ix_auth_rate_limit_type_expiry', 'bucket_type', 'expires_at'),
    )


class AdminRole(Base):
    """Seeded admin role metadata for the RBAC compatibility layer."""

    __tablename__ = 'admin_roles'

    role_key = Column(String(64), primary_key=True)
    display_name = Column(String(128), nullable=False)
    description = Column(Text)
    built_in = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class AdminRoleCapability(Base):
    """Seeded role-to-capability mapping for read-only expansion."""

    __tablename__ = 'admin_role_capabilities'

    id = Column(Integer, primary_key=True, autoincrement=True)
    role_key = Column(String(64), ForeignKey('admin_roles.role_key'), nullable=False, index=True)
    capability = Column(String(96), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.now, index=True)

    __table_args__ = (
        UniqueConstraint('role_key', 'capability', name='uix_admin_role_capability'),
        Index('ix_admin_role_capability_lookup', 'role_key', 'capability'),
    )


class AdminUserRole(Base):
    """Optional explicit user-to-admin-role assignment for future phases."""

    __tablename__ = 'admin_user_roles'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), ForeignKey('app_users.id'), nullable=False, index=True)
    role_key = Column(String(64), ForeignKey('admin_roles.role_key'), nullable=False, index=True)
    assigned_at = Column(DateTime, default=datetime.now, index=True)
    assigned_by = Column(String(64))

    __table_args__ = (
        UniqueConstraint('user_id', 'role_key', name='uix_admin_user_role'),
        Index('ix_admin_user_role_lookup', 'user_id', 'role_key'),
    )


class UserPreference(Base):
    """User-owned preferences kept separate from global system configuration."""

    __tablename__ = 'user_preferences'

    user_id = Column(String(64), ForeignKey('app_users.id'), primary_key=True)
    ui_preferences_json = Column(Text)
    notification_preferences_json = Column(Text)
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class AnalysisHistory(Base):
    """
    分析结果历史记录模型

    保存每次分析结果，支持按 query_id/股票代码检索
    """
    __tablename__ = 'analysis_history'

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(String(64), ForeignKey('app_users.id'), index=True, default=BOOTSTRAP_ADMIN_USER_ID)

    # 关联查询链路
    query_id = Column(String(64), index=True)

    # 股票信息
    code = Column(String(10), nullable=False, index=True)
    name = Column(String(50))
    report_type = Column(String(16), index=True)

    # 核心结论
    sentiment_score = Column(Integer)
    operation_advice = Column(String(20))
    trend_prediction = Column(String(50))
    analysis_summary = Column(Text)

    # 详细数据
    raw_result = Column(Text)
    news_content = Column(Text)
    context_snapshot = Column(Text)

    # 狙击点位（用于回测）
    ideal_buy = Column(Float)
    secondary_buy = Column(Float)
    stop_loss = Column(Float)
    take_profit = Column(Float)
    is_test = Column(Boolean, nullable=False, default=False, index=True)

    created_at = Column(DateTime, default=datetime.now, index=True)

    __table_args__ = (
        Index('ix_analysis_owner_created', 'owner_id', 'created_at'),
        Index('ix_analysis_owner_query', 'owner_id', 'query_id'),
        Index('ix_analysis_code_time', 'code', 'created_at'),
    )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'owner_id': self.owner_id,
            'query_id': self.query_id,
            'code': self.code,
            'name': self.name,
            'report_type': self.report_type,
            'sentiment_score': self.sentiment_score,
            'operation_advice': self.operation_advice,
            'trend_prediction': self.trend_prediction,
            'analysis_summary': self.analysis_summary,
            'raw_result': self.raw_result,
            'news_content': self.news_content,
            'context_snapshot': self.context_snapshot,
            'ideal_buy': self.ideal_buy,
            'secondary_buy': self.secondary_buy,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'is_test': bool(self.is_test),
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class DurableTaskState(Base):
    """
    Durable task/progress state for owner-scoped status reads.

    This is a WS2-R1 foundation table. It mirrors process-local task state and
    deliberately stores only bounded, sanitized metadata.
    """

    __tablename__ = 'durable_task_states'

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(64), nullable=False, unique=True, index=True)
    owner_user_id = Column(String(64), ForeignKey('app_users.id'), nullable=False, index=True)
    task_type = Column(String(32), nullable=False, index=True)
    route_family = Column(String(64))
    status = Column(String(32), nullable=False, index=True)
    progress = Column(Integer, nullable=False, default=0)
    current_step = Column(Text)
    error_code = Column(String(64))
    error_summary = Column(Text)
    attempt_count = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=1)
    lease_owner = Column(String(128), index=True)
    lease_expires_at = Column(DateTime, index=True)
    idempotency_key_hash = Column(String(128), index=True)
    dedupe_key_hash = Column(String(128), index=True)
    active_dedupe_key_hash = Column(String(128), index=True)
    metadata_json = Column(Text)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False, index=True)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    failed_at = Column(DateTime)
    cancelled_at = Column(DateTime)

    __table_args__ = (
        Index('ix_durable_task_owner_created', 'owner_user_id', 'created_at'),
        Index('ix_durable_task_owner_status_created', 'owner_user_id', 'status', 'created_at'),
        Index('ix_durable_task_status_updated', 'status', 'updated_at'),
        Index('ix_durable_task_status_lease', 'status', 'lease_expires_at'),
        Index(
            'ux_durable_task_active_dedupe',
            'owner_user_id',
            'task_type',
            'active_dedupe_key_hash',
            unique=True,
        ),
    )

    def to_dict(self) -> Dict[str, Any]:
        metadata = DatabaseManager._safe_json_loads(self.metadata_json, {}) if self.metadata_json else {}
        if not isinstance(metadata, dict):
            metadata = {}
        return {
            'task_id': self.task_id,
            'owner_user_id': self.owner_user_id,
            'task_type': self.task_type,
            'route_family': self.route_family,
            'status': self.status,
            'progress': int(self.progress or 0),
            'current_step': self.current_step,
            'error_code': self.error_code,
            'error_summary': self.error_summary,
            'attempt_count': int(self.attempt_count or 0),
            'max_attempts': int(self.max_attempts or 1),
            'lease_owner': self.lease_owner,
            'lease_expires_at': self.lease_expires_at.isoformat() if self.lease_expires_at else None,
            'metadata': metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'failed_at': self.failed_at.isoformat() if self.failed_at else None,
            'cancelled_at': self.cancelled_at.isoformat() if self.cancelled_at else None,
        }


class DurableTaskProgressEvent(Base):
    """Replayable, owner-scoped durable task progress event."""

    __tablename__ = 'durable_task_progress_events'

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(64), nullable=False, index=True)
    owner_user_id = Column(String(64), ForeignKey('app_users.id'), nullable=False, index=True)
    sequence = Column(Integer, nullable=False)
    event_type = Column(String(32), nullable=False)
    stage = Column(String(64))
    progress = Column(Integer)
    message_safe = Column(Text)
    metadata_json = Column(Text)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint('task_id', 'sequence', name='uq_durable_task_progress_task_sequence'),
        Index('ix_durable_task_progress_task_sequence', 'task_id', 'sequence'),
        Index('ix_durable_task_progress_task_created', 'task_id', 'created_at'),
        Index('ix_durable_task_progress_owner_created', 'owner_user_id', 'created_at'),
    )

    def to_dict(self) -> Dict[str, Any]:
        metadata = DatabaseManager._safe_json_loads(self.metadata_json, {}) if self.metadata_json else {}
        if not isinstance(metadata, dict):
            metadata = {}
        return {
            'task_id': self.task_id,
            'owner_user_id': self.owner_user_id,
            'sequence': int(self.sequence or 0),
            'event_type': self.event_type,
            'stage': self.stage,
            'progress': int(self.progress) if self.progress is not None else None,
            'message_safe': self.message_safe,
            'metadata': metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class QuotaPolicyDefinition(Base):
    """WS2 quota policy definition, not wired into live route enforcement."""

    __tablename__ = 'quota_policy_definitions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    policy_key = Column(String(128), nullable=False, unique=True, index=True)
    scope_type = Column(String(32), nullable=False, index=True)
    route_family = Column(String(64), index=True)
    provider = Column(String(64), index=True)
    model_tier = Column(String(64), index=True)
    daily_budget_units = Column(Integer)
    monthly_budget_units = Column(Integer)
    token_cap = Column(Integer)
    request_cap = Column(Integer)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    metadata_json = Column(Text)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False, index=True)

    __table_args__ = (
        Index('ix_quota_policy_scope_route', 'scope_type', 'route_family'),
        Index('ix_quota_policy_scope_provider', 'scope_type', 'provider', 'model_tier'),
    )

    def to_dict(self) -> Dict[str, Any]:
        metadata = DatabaseManager._safe_json_loads(self.metadata_json, {}) if self.metadata_json else {}
        if not isinstance(metadata, dict):
            metadata = {}
        return {
            'policy_key': self.policy_key,
            'scope_type': self.scope_type,
            'route_family': self.route_family,
            'provider': self.provider,
            'model_tier': self.model_tier,
            'daily_budget_units': self.daily_budget_units,
            'monthly_budget_units': self.monthly_budget_units,
            'token_cap': self.token_cap,
            'request_cap': self.request_cap,
            'enabled': bool(self.enabled),
            'metadata': metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class QuotaUsageWindow(Base):
    """Reserved/consumed quota units for one bounded accounting window."""

    __tablename__ = 'quota_usage_windows'

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_user_id = Column(String(64), ForeignKey('app_users.id'), nullable=True, index=True)
    route_family = Column(String(64), index=True)
    provider = Column(String(64), index=True)
    model_tier = Column(String(64), index=True)
    window_identity_key = Column(String(512), nullable=False, default="", index=True)
    window_type = Column(String(16), nullable=False, index=True)
    window_start = Column(DateTime, nullable=False, index=True)
    window_end = Column(DateTime, nullable=False, index=True)
    reserved_units = Column(Integer, nullable=False, default=0)
    consumed_units = Column(Integer, nullable=False, default=0)
    request_count = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False, index=True)

    __table_args__ = (
        Index('ix_quota_window_owner_type_start', 'owner_user_id', 'window_type', 'window_start'),
        Index('ix_quota_window_route_type_start', 'route_family', 'window_type', 'window_start'),
        Index('ix_quota_window_provider_type_start', 'provider', 'model_tier', 'window_type', 'window_start'),
        Index('ux_quota_window_identity', 'window_identity_key', 'window_type', 'window_start', unique=True),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'owner_user_id': self.owner_user_id,
            'route_family': self.route_family,
            'provider': self.provider,
            'model_tier': self.model_tier,
            'window_type': self.window_type,
            'window_start': self.window_start.isoformat() if self.window_start else None,
            'window_end': self.window_end.isoformat() if self.window_end else None,
            'reserved_units': int(self.reserved_units or 0),
            'consumed_units': int(self.consumed_units or 0),
            'request_count': int(self.request_count or 0),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class QuotaReservation(Base):
    """Synthetic quota reservation lifecycle row."""

    __tablename__ = 'quota_reservations'

    id = Column(Integer, primary_key=True, autoincrement=True)
    reservation_id = Column(String(64), nullable=False, unique=True, index=True)
    owner_user_id = Column(String(64), ForeignKey('app_users.id'), nullable=True, index=True)
    route_family = Column(String(64), index=True)
    provider = Column(String(64), index=True)
    model_tier = Column(String(64), index=True)
    request_idempotency_key_hash = Column(String(128), index=True)
    estimated_units = Column(Integer, nullable=False, default=0)
    status = Column(String(16), nullable=False, index=True)
    reason_code = Column(String(64), index=True)
    metadata_json = Column(Text)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)

    __table_args__ = (
        Index('ix_quota_reservation_owner_status_created', 'owner_user_id', 'status', 'created_at'),
        Index('ix_quota_reservation_route_status_created', 'route_family', 'status', 'created_at'),
        Index('ix_quota_reservation_status_expires', 'status', 'expires_at'),
        Index('ux_quota_reservation_request_idempotency', 'request_idempotency_key_hash', unique=True),
    )

    def to_dict(self) -> Dict[str, Any]:
        metadata = DatabaseManager._safe_json_loads(self.metadata_json, {}) if self.metadata_json else {}
        if not isinstance(metadata, dict):
            metadata = {}
        return {
            'reservation_id': self.reservation_id,
            'owner_user_id': self.owner_user_id,
            'route_family': self.route_family,
            'provider': self.provider,
            'model_tier': self.model_tier,
            'estimated_units': int(self.estimated_units or 0),
            'status': self.status,
            'reason_code': self.reason_code,
            'metadata': metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
        }


class ModelPricingPolicy(Base):
    """Effective-dated LLM model pricing policy foundation."""

    __tablename__ = 'model_pricing_policies'

    id = Column(Integer, primary_key=True, autoincrement=True)
    policy_key = Column(String(160), nullable=False, unique=True, index=True)
    provider = Column(String(64), nullable=False, index=True)
    model = Column(String(128), nullable=False, index=True)
    pricing_unit = Column(String(32), nullable=False, default="per_1m_tokens")
    input_price_per_1m = Column(Numeric(18, 8), nullable=False, default=0)
    cached_input_price_per_1m = Column(Numeric(18, 8))
    output_price_per_1m = Column(Numeric(18, 8), nullable=False, default=0)
    currency = Column(String(8), nullable=False, default="USD", index=True)
    effective_from = Column(DateTime, nullable=False, index=True)
    effective_until = Column(DateTime, index=True)
    source_label = Column(String(128))
    source_url = Column(String(500))
    active = Column(Boolean, nullable=False, default=True, index=True)
    metadata_json = Column(Text)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False, index=True)

    __table_args__ = (
        Index('ix_model_pricing_provider_model_effective', 'provider', 'model', 'active', 'effective_from', 'effective_until'),
        Index('ix_model_pricing_active_updated', 'active', 'updated_at'),
    )

    def to_dict(self) -> Dict[str, Any]:
        metadata = DatabaseManager._safe_json_loads(self.metadata_json, {}) if self.metadata_json else {}
        if not isinstance(metadata, dict):
            metadata = {}
        return {
            'policy_key': self.policy_key,
            'provider': self.provider,
            'model': self.model,
            'pricing_unit': self.pricing_unit,
            'input_price_per_1m': str(self.input_price_per_1m or 0),
            'cached_input_price_per_1m': str(self.cached_input_price_per_1m) if self.cached_input_price_per_1m is not None else None,
            'output_price_per_1m': str(self.output_price_per_1m or 0),
            'currency': self.currency,
            'effective_from': self.effective_from.isoformat() if self.effective_from else None,
            'effective_until': self.effective_until.isoformat() if self.effective_until else None,
            'source_label': self.source_label,
            'source_url': self.source_url,
            'active': bool(self.active),
            'metadata': metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class LLMCostLedger(Base):
    """Durable estimated LLM cost ledger, separate from live enforcement."""

    __tablename__ = 'llm_cost_ledger'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ledger_id = Column(String(64), nullable=False, unique=True, index=True)
    owner_user_id = Column(String(64), ForeignKey('app_users.id'), nullable=True, index=True)
    guest_bucket_hash = Column(String(128), index=True)
    route_family = Column(String(64), nullable=False, index=True)
    call_type = Column(String(64), nullable=False, index=True)
    provider = Column(String(64), nullable=False, index=True)
    model = Column(String(128), nullable=False, index=True)
    prompt_tokens = Column(Integer, nullable=False, default=0)
    cached_input_tokens = Column(Integer, nullable=False, default=0)
    cache_miss_input_tokens = Column(Integer, nullable=False, default=0)
    completion_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    input_cost_usd = Column(Numeric(18, 8), nullable=False, default=0)
    cached_input_cost_usd = Column(Numeric(18, 8), nullable=False, default=0)
    output_cost_usd = Column(Numeric(18, 8), nullable=False, default=0)
    total_cost_usd = Column(Numeric(18, 8), nullable=False, default=0)
    pricing_policy_key = Column(String(160), index=True)
    pricing_snapshot_json = Column(Text)
    quota_reservation_id = Column(String(64), index=True)
    request_hash = Column(String(128), index=True)
    status = Column(String(32), nullable=False, default="ok", index=True)
    metadata_json = Column(Text)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)

    __table_args__ = (
        Index('ix_llm_cost_ledger_owner_created', 'owner_user_id', 'created_at'),
        Index('ix_llm_cost_ledger_owner_route_created', 'owner_user_id', 'route_family', 'created_at'),
        Index('ix_llm_cost_ledger_provider_model_created', 'provider', 'model', 'created_at'),
        Index('ix_llm_cost_ledger_route_created', 'route_family', 'created_at'),
    )

    def to_dict(self) -> Dict[str, Any]:
        metadata = DatabaseManager._safe_json_loads(self.metadata_json, {}) if self.metadata_json else {}
        if not isinstance(metadata, dict):
            metadata = {}
        snapshot = DatabaseManager._safe_json_loads(self.pricing_snapshot_json, {}) if self.pricing_snapshot_json else {}
        if not isinstance(snapshot, dict):
            snapshot = {}
        return {
            'ledger_id': self.ledger_id,
            'owner_user_id': self.owner_user_id,
            'guest_bucket_hash': self.guest_bucket_hash,
            'route_family': self.route_family,
            'call_type': self.call_type,
            'provider': self.provider,
            'model': self.model,
            'prompt_tokens': int(self.prompt_tokens or 0),
            'cached_input_tokens': int(self.cached_input_tokens or 0),
            'cache_miss_input_tokens': int(self.cache_miss_input_tokens or 0),
            'completion_tokens': int(self.completion_tokens or 0),
            'total_tokens': int(self.total_tokens or 0),
            'input_cost_usd': str(self.input_cost_usd or 0),
            'cached_input_cost_usd': str(self.cached_input_cost_usd or 0),
            'output_cost_usd': str(self.output_cost_usd or 0),
            'total_cost_usd': str(self.total_cost_usd or 0),
            'pricing_policy_key': self.pricing_policy_key,
            'pricing_snapshot': snapshot,
            'quota_reservation_id': self.quota_reservation_id,
            'request_hash': self.request_hash,
            'status': self.status,
            'metadata': metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ProviderQuotaPolicy(Base):
    """Provider quota policy foundation, not wired into runtime enforcement."""

    __tablename__ = 'provider_quota_policies'

    id = Column(Integer, primary_key=True, autoincrement=True)
    policy_key = Column(String(128), nullable=False, unique=True, index=True)
    scope_type = Column(String(32), nullable=False, index=True)
    owner_user_id = Column(String(64), ForeignKey('app_users.id'), nullable=True, index=True)
    guest_bucket_hash = Column(String(128), index=True)
    provider = Column(String(64), nullable=False, index=True)
    provider_category = Column(String(64), index=True)
    route_family = Column(String(64), index=True)
    window_type = Column(String(16), nullable=False, index=True)
    request_cap = Column(Integer)
    budget_unit_cap = Column(Integer)
    retry_cap = Column(Integer)
    timeout_cap_ms = Column(Integer)
    fallback_cap = Column(Integer)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    effective_from = Column(DateTime)
    effective_until = Column(DateTime)
    metadata_json = Column(Text)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False, index=True)

    __table_args__ = (
        Index('ix_provider_quota_policy_provider_route', 'scope_type', 'provider', 'provider_category', 'route_family', 'enabled'),
        Index('ix_provider_quota_policy_owner_provider', 'owner_user_id', 'provider', 'provider_category', 'route_family', 'enabled'),
        Index('ix_provider_quota_policy_guest_provider', 'guest_bucket_hash', 'provider', 'route_family', 'enabled'),
        Index('ix_provider_quota_policy_effective', 'enabled', 'effective_from', 'effective_until'),
        Index('ix_provider_quota_policy_dashboard', 'provider', 'route_family', 'updated_at'),
    )

    def to_dict(self) -> Dict[str, Any]:
        metadata = DatabaseManager._safe_json_loads(self.metadata_json, {}) if self.metadata_json else {}
        if not isinstance(metadata, dict):
            metadata = {}
        return {
            'policy_key': self.policy_key,
            'scope_type': self.scope_type,
            'owner_user_id': self.owner_user_id,
            'guest_bucket_hash': self.guest_bucket_hash,
            'provider': self.provider,
            'provider_category': self.provider_category,
            'route_family': self.route_family,
            'window_type': self.window_type,
            'request_cap': self.request_cap,
            'budget_unit_cap': self.budget_unit_cap,
            'retry_cap': self.retry_cap,
            'timeout_cap_ms': self.timeout_cap_ms,
            'fallback_cap': self.fallback_cap,
            'enabled': bool(self.enabled),
            'effective_from': self.effective_from.isoformat() if self.effective_from else None,
            'effective_until': self.effective_until.isoformat() if self.effective_until else None,
            'metadata': metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class ProviderQuotaWindow(Base):
    """Provider request/unit counters for one synthetic accounting window."""

    __tablename__ = 'provider_quota_windows'

    id = Column(Integer, primary_key=True, autoincrement=True)
    policy_key = Column(String(128), index=True)
    owner_user_id = Column(String(64), ForeignKey('app_users.id'), nullable=True, index=True)
    guest_bucket_hash = Column(String(128), index=True)
    provider = Column(String(64), nullable=False, index=True)
    provider_category = Column(String(64), index=True)
    route_family = Column(String(64), index=True)
    window_type = Column(String(16), nullable=False, index=True)
    window_start = Column(DateTime, nullable=False, index=True)
    window_end = Column(DateTime, nullable=False, index=True)
    request_count = Column(Integer, nullable=False, default=0)
    reserved_units = Column(Integer, nullable=False, default=0)
    consumed_units = Column(Integer, nullable=False, default=0)
    released_units = Column(Integer, nullable=False, default=0)
    rejected_count = Column(Integer, nullable=False, default=0)
    success_count = Column(Integer, nullable=False, default=0)
    failure_count = Column(Integer, nullable=False, default=0)
    timeout_count = Column(Integer, nullable=False, default=0)
    provider_429_count = Column(Integer, nullable=False, default=0)
    provider_403_count = Column(Integer, nullable=False, default=0)
    fallback_count = Column(Integer, nullable=False, default=0)
    probe_count = Column(Integer, nullable=False, default=0)
    cache_only_count = Column(Integer, nullable=False, default=0)
    stale_served_count = Column(Integer, nullable=False, default=0)
    metadata_json = Column(Text)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False, index=True)

    __table_args__ = (
        Index('ix_provider_quota_window_owner_provider', 'owner_user_id', 'provider', 'route_family', 'window_start', 'window_end'),
        Index('ix_provider_quota_window_provider_route', 'provider', 'provider_category', 'route_family', 'window_start', 'window_end'),
        Index('ix_provider_quota_window_probe', 'provider', 'route_family', 'provider_category', 'window_start'),
        Index('ix_provider_quota_window_updated', 'updated_at'),
        Index('ix_provider_quota_window_start', 'window_start'),
        Index('ix_provider_quota_window_end', 'window_end'),
        Index('ix_provider_quota_window_burn', 'provider', 'route_family', 'consumed_units', 'window_end'),
    )

    def to_dict(self) -> Dict[str, Any]:
        metadata = DatabaseManager._safe_json_loads(self.metadata_json, {}) if self.metadata_json else {}
        if not isinstance(metadata, dict):
            metadata = {}
        return {
            'policy_key': self.policy_key,
            'owner_user_id': self.owner_user_id,
            'guest_bucket_hash': self.guest_bucket_hash,
            'provider': self.provider,
            'provider_category': self.provider_category,
            'route_family': self.route_family,
            'window_type': self.window_type,
            'window_start': self.window_start.isoformat() if self.window_start else None,
            'window_end': self.window_end.isoformat() if self.window_end else None,
            'request_count': int(self.request_count or 0),
            'reserved_units': int(self.reserved_units or 0),
            'consumed_units': int(self.consumed_units or 0),
            'released_units': int(self.released_units or 0),
            'rejected_count': int(self.rejected_count or 0),
            'success_count': int(self.success_count or 0),
            'failure_count': int(self.failure_count or 0),
            'timeout_count': int(self.timeout_count or 0),
            'provider_429_count': int(self.provider_429_count or 0),
            'provider_403_count': int(self.provider_403_count or 0),
            'fallback_count': int(self.fallback_count or 0),
            'probe_count': int(self.probe_count or 0),
            'cache_only_count': int(self.cache_only_count or 0),
            'stale_served_count': int(self.stale_served_count or 0),
            'metadata': metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class ProviderCircuitState(Base):
    """Current durable provider circuit state for future read-only checks."""

    __tablename__ = 'provider_circuit_states'

    id = Column(Integer, primary_key=True, autoincrement=True)
    scope_type = Column(String(32), nullable=False, index=True)
    owner_user_id = Column(String(64), ForeignKey('app_users.id'), nullable=True, index=True)
    guest_bucket_hash = Column(String(128), index=True)
    provider = Column(String(64), nullable=False, index=True)
    provider_category = Column(String(64), index=True)
    route_family = Column(String(64), index=True)
    state = Column(String(32), nullable=False, index=True)
    reason_bucket = Column(String(64), index=True)
    previous_state = Column(String(32))
    opened_at = Column(DateTime)
    cooldown_until = Column(DateTime, index=True)
    half_open_started_at = Column(DateTime)
    half_open_sample_limit = Column(Integer, nullable=False, default=0)
    half_open_sample_count = Column(Integer, nullable=False, default=0)
    success_sample_count = Column(Integer, nullable=False, default=0)
    failure_sample_count = Column(Integer, nullable=False, default=0)
    failure_count = Column(Integer, nullable=False, default=0)
    success_count = Column(Integer, nullable=False, default=0)
    last_transition_event_id = Column(Integer, index=True)
    operator_action_ref = Column(String(128), index=True)
    metadata_json = Column(Text)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False, index=True)

    __table_args__ = (
        Index('ix_provider_circuit_state_provider_route', 'provider', 'provider_category', 'route_family', 'state'),
        Index('ix_provider_circuit_state_cooldown', 'provider', 'cooldown_until'),
        Index('ix_provider_circuit_state_owner', 'owner_user_id', 'provider', 'route_family', 'state'),
        Index('ix_provider_circuit_state_guest', 'guest_bucket_hash', 'provider', 'route_family', 'state'),
        Index('ix_provider_circuit_state_status_updated', 'state', 'updated_at'),
        Index('ix_provider_circuit_state_provider_status', 'provider', 'state', 'updated_at'),
    )

    def to_dict(self) -> Dict[str, Any]:
        metadata = DatabaseManager._safe_json_loads(self.metadata_json, {}) if self.metadata_json else {}
        if not isinstance(metadata, dict):
            metadata = {}
        return {
            'id': self.id,
            'scope_type': self.scope_type,
            'owner_user_id': self.owner_user_id,
            'guest_bucket_hash': self.guest_bucket_hash,
            'provider': self.provider,
            'provider_category': self.provider_category,
            'route_family': self.route_family,
            'state': self.state,
            'reason_bucket': self.reason_bucket,
            'previous_state': self.previous_state,
            'opened_at': self.opened_at.isoformat() if self.opened_at else None,
            'cooldown_until': self.cooldown_until.isoformat() if self.cooldown_until else None,
            'half_open_started_at': self.half_open_started_at.isoformat() if self.half_open_started_at else None,
            'half_open_sample_limit': int(self.half_open_sample_limit or 0),
            'half_open_sample_count': int(self.half_open_sample_count or 0),
            'success_sample_count': int(self.success_sample_count or 0),
            'failure_sample_count': int(self.failure_sample_count or 0),
            'failure_count': int(self.failure_count or 0),
            'success_count': int(self.success_count or 0),
            'last_transition_event_id': self.last_transition_event_id,
            'operator_action_ref': self.operator_action_ref,
            'metadata': metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class ProviderCircuitEvent(Base):
    """Append-only provider circuit transition and policy event history."""

    __tablename__ = 'provider_circuit_events'

    id = Column(Integer, primary_key=True, autoincrement=True)
    state_id = Column(Integer, index=True)
    event_type = Column(String(32), nullable=False, index=True)
    from_state = Column(String(32), index=True)
    to_state = Column(String(32), index=True)
    reason_bucket = Column(String(64), index=True)
    owner_user_id = Column(String(64), ForeignKey('app_users.id'), nullable=True, index=True)
    guest_bucket_hash = Column(String(128), index=True)
    provider = Column(String(64), nullable=False, index=True)
    provider_category = Column(String(64), index=True)
    route_family = Column(String(64), index=True)
    request_count_bucket = Column(String(32))
    duration_bucket_ms = Column(Integer)
    failure_count_bucket = Column(String(32))
    quota_window_start = Column(DateTime)
    quota_window_end = Column(DateTime)
    operator_action_ref = Column(String(128), index=True)
    metadata_json = Column(Text)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)

    __table_args__ = (
        Index('ix_provider_circuit_event_created', 'created_at'),
        Index('ix_provider_circuit_event_provider_time', 'provider', 'provider_category', 'route_family', 'created_at'),
        Index('ix_provider_circuit_event_to_state_time', 'to_state', 'created_at'),
        Index('ix_provider_circuit_event_operator_time', 'operator_action_ref', 'created_at'),
        Index('ix_provider_circuit_event_owner_time', 'owner_user_id', 'created_at'),
        Index('ix_provider_circuit_event_type_time', 'event_type', 'created_at'),
        Index('ix_provider_circuit_event_reason_time', 'reason_bucket', 'created_at'),
    )

    def to_dict(self) -> Dict[str, Any]:
        metadata = DatabaseManager._safe_json_loads(self.metadata_json, {}) if self.metadata_json else {}
        if not isinstance(metadata, dict):
            metadata = {}
        return {
            'id': self.id,
            'state_id': self.state_id,
            'event_type': self.event_type,
            'from_state': self.from_state,
            'to_state': self.to_state,
            'reason_bucket': self.reason_bucket,
            'owner_user_id': self.owner_user_id,
            'guest_bucket_hash': self.guest_bucket_hash,
            'provider': self.provider,
            'provider_category': self.provider_category,
            'route_family': self.route_family,
            'request_count_bucket': self.request_count_bucket,
            'duration_bucket_ms': self.duration_bucket_ms,
            'failure_count_bucket': self.failure_count_bucket,
            'quota_window_start': self.quota_window_start.isoformat() if self.quota_window_start else None,
            'quota_window_end': self.quota_window_end.isoformat() if self.quota_window_end else None,
            'operator_action_ref': self.operator_action_ref,
            'metadata': metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ProviderProbeEvent(Base):
    """Bounded admin or synthetic probe event storage, separate from live provider calls."""

    __tablename__ = 'provider_probe_events'

    id = Column(Integer, primary_key=True, autoincrement=True)
    probe_type = Column(String(32), nullable=False, index=True)
    probe_source = Column(String(32), nullable=False, index=True)
    actor_user_id = Column(String(64), ForeignKey('app_users.id'), nullable=True, index=True)
    provider = Column(String(64), nullable=False, index=True)
    provider_category = Column(String(64), index=True)
    route_family = Column(String(64), index=True)
    state_id = Column(Integer, index=True)
    result_bucket = Column(String(64), nullable=False, index=True)
    duration_bucket_ms = Column(Integer)
    metadata_json = Column(Text)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)

    __table_args__ = (
        Index('ix_provider_probe_event_provider_time', 'provider', 'provider_category', 'probe_type', 'created_at'),
        Index('ix_provider_probe_event_actor_time', 'actor_user_id', 'created_at'),
        Index('ix_provider_probe_event_result_time', 'result_bucket', 'created_at'),
        Index('ix_provider_probe_event_state_time', 'state_id', 'created_at'),
        Index('ix_provider_probe_event_created', 'created_at'),
    )

    def to_dict(self) -> Dict[str, Any]:
        metadata = DatabaseManager._safe_json_loads(self.metadata_json, {}) if self.metadata_json else {}
        if not isinstance(metadata, dict):
            metadata = {}
        return {
            'id': self.id,
            'probe_type': self.probe_type,
            'probe_source': self.probe_source,
            'actor_user_id': self.actor_user_id,
            'provider': self.provider,
            'provider_category': self.provider_category,
            'route_family': self.route_family,
            'state_id': self.state_id,
            'result_bucket': self.result_bucket,
            'duration_bucket_ms': self.duration_bucket_ms,
            'metadata': metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ExecutionLogSession(Base):
    """
    管理员可观测执行会话（D2）。

    每次分析任务对应一个会话，存储执行总体状态与关联信息。
    """

    __tablename__ = 'execution_log_sessions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, unique=True, index=True)
    task_id = Column(String(64), index=True)
    query_id = Column(String(64), index=True)
    analysis_history_id = Column(Integer, ForeignKey('analysis_history.id'), index=True)
    code = Column(String(10), index=True)
    name = Column(String(50))
    overall_status = Column(String(32), nullable=False, default='running', index=True)
    truth_level = Column(String(16), nullable=False, default='mixed')
    summary_json = Column(Text)
    started_at = Column(DateTime, default=datetime.now, index=True)
    ended_at = Column(DateTime, index=True)
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index('ix_exec_session_code_started', 'code', 'started_at'),
        Index('ix_exec_session_query_started', 'query_id', 'started_at'),
    )


class ExecutionLogEvent(Base):
    """
    执行会话的结构化事件流（D2）。

    phase 示例：
    - ai
    - data.market / data.fundamentals / data.news / data.sentiment
    - notification
    """

    __tablename__ = 'execution_log_events'

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True)
    event_at = Column(DateTime, default=datetime.now, index=True)
    phase = Column(String(48), nullable=False, index=True)
    step = Column(String(48), index=True)
    target = Column(String(128), index=True)
    status = Column(String(32), nullable=False, index=True)
    truth_level = Column(String(16), nullable=False, default='inferred', index=True)
    message = Column(Text)
    error_code = Column(String(64))
    detail_json = Column(Text)

    __table_args__ = (
        Index('ix_exec_event_session_time', 'session_id', 'event_at'),
        Index('ix_exec_event_phase_status', 'phase', 'status'),
    )


class NotificationChannel(Base):
    """Admin-managed operational notification channel."""

    __tablename__ = 'notification_channels'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(80), nullable=False)
    type = Column(String(16), nullable=False, index=True)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    severity_min = Column(String(16), nullable=False, default='warning', index=True)
    event_types_json = Column(Text)
    config_json = Column(Text)
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    last_tested_at = Column(DateTime)
    last_sent_at = Column(DateTime)
    last_error = Column(Text)

    __table_args__ = (
        Index('ix_notification_channel_enabled_type', 'enabled', 'type'),
    )


class NotificationEvent(Base):
    """In-app admin notification event and outbound delivery audit state."""

    __tablename__ = 'notification_events'

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(80), nullable=False, index=True)
    severity = Column(String(16), nullable=False, index=True)
    title = Column(String(160), nullable=False)
    message = Column(Text)
    payload_json = Column(Text)
    fingerprint = Column(String(160), index=True)
    dedupe_key = Column(String(255), index=True)
    delivery_status = Column(String(24), nullable=False, default='pending', index=True)
    created_at = Column(DateTime, default=datetime.now, index=True)
    acknowledged_at = Column(DateTime)
    acknowledged_by = Column(String(64))

    __table_args__ = (
        Index('ix_notification_event_type_severity_time', 'event_type', 'severity', 'created_at'),
        Index('ix_notification_event_dedupe_time', 'dedupe_key', 'created_at'),
    )


class BacktestResult(Base):
    """单条分析记录的回测结果。"""

    __tablename__ = 'backtest_results'

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(String(64), ForeignKey('app_users.id'), index=True, default=BOOTSTRAP_ADMIN_USER_ID)

    analysis_history_id = Column(
        Integer,
        ForeignKey('analysis_history.id'),
        nullable=False,
        index=True,
    )

    # 冗余字段，便于按股票筛选
    code = Column(String(10), nullable=False, index=True)
    analysis_date = Column(Date, index=True)

    # 回测参数
    eval_window_days = Column(Integer, nullable=False, default=10)
    engine_version = Column(String(16), nullable=False, default='v1')

    # 状态
    eval_status = Column(String(16), nullable=False, default='pending')
    evaluated_at = Column(DateTime, default=datetime.now, index=True)

    # 建议快照（避免未来分析字段变化导致回测不可解释）
    operation_advice = Column(String(20))
    position_recommendation = Column(String(8))  # long/cash

    # 价格与收益
    start_price = Column(Float)
    end_close = Column(Float)
    max_high = Column(Float)
    min_low = Column(Float)
    stock_return_pct = Column(Float)

    # 方向与结果
    direction_expected = Column(String(16))  # up/down/flat/not_down
    direction_correct = Column(Boolean, nullable=True)
    outcome = Column(String(16))  # win/loss/neutral

    # 目标价命中（仅 long 且配置了止盈/止损时有意义）
    stop_loss = Column(Float)
    take_profit = Column(Float)
    hit_stop_loss = Column(Boolean)
    hit_take_profit = Column(Boolean)
    first_hit = Column(String(16))  # take_profit/stop_loss/ambiguous/neither/not_applicable
    first_hit_date = Column(Date)
    first_hit_trading_days = Column(Integer)

    # 模拟执行（long-only）
    simulated_entry_price = Column(Float)
    simulated_exit_price = Column(Float)
    simulated_exit_reason = Column(String(24))  # stop_loss/take_profit/window_end/cash/ambiguous_stop_loss
    simulated_return_pct = Column(Float)

    __table_args__ = (
        UniqueConstraint(
            'analysis_history_id',
            'eval_window_days',
            'engine_version',
            name='uix_backtest_analysis_window_version',
        ),
        Index('ix_backtest_result_owner_evaluated', 'owner_id', 'evaluated_at'),
        Index('ix_backtest_code_date', 'code', 'analysis_date'),
    )


class BacktestSummary(Base):
    """回测汇总指标（按股票或全局）。"""

    __tablename__ = 'backtest_summaries'

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(String(64), ForeignKey('app_users.id'), nullable=False, index=True, default=BOOTSTRAP_ADMIN_USER_ID)

    scope = Column(String(16), nullable=False, index=True)  # overall/stock
    code = Column(String(16), index=True)

    eval_window_days = Column(Integer, nullable=False, default=10)
    engine_version = Column(String(16), nullable=False, default='v1')
    computed_at = Column(DateTime, default=datetime.now, index=True)

    # 计数
    total_evaluations = Column(Integer, default=0)
    completed_count = Column(Integer, default=0)
    insufficient_count = Column(Integer, default=0)
    long_count = Column(Integer, default=0)
    cash_count = Column(Integer, default=0)

    win_count = Column(Integer, default=0)
    loss_count = Column(Integer, default=0)
    neutral_count = Column(Integer, default=0)

    # 准确率/胜率
    direction_accuracy_pct = Column(Float)
    win_rate_pct = Column(Float)
    neutral_rate_pct = Column(Float)

    # 收益
    avg_stock_return_pct = Column(Float)
    avg_simulated_return_pct = Column(Float)

    # 目标价触发统计（仅 long 且配置止盈/止损时统计）
    stop_loss_trigger_rate = Column(Float)
    take_profit_trigger_rate = Column(Float)
    ambiguous_rate = Column(Float)
    avg_days_to_first_hit = Column(Float)

    # 诊断字段（JSON 字符串）
    advice_breakdown_json = Column(Text)
    diagnostics_json = Column(Text)

    __table_args__ = (
        UniqueConstraint(
            'owner_id',
            'scope',
            'code',
            'eval_window_days',
            'engine_version',
            name='uix_backtest_summary_owner_scope_code_window_version',
        ),
    )


class BacktestRun(Base):
    """One persisted backtest execution."""

    __tablename__ = 'backtest_runs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(String(64), ForeignKey('app_users.id'), index=True, default=BOOTSTRAP_ADMIN_USER_ID)

    code = Column(String(16), index=True)
    eval_window_days = Column(Integer, nullable=False, default=10, index=True)
    min_age_days = Column(Integer, nullable=False, default=14)
    force = Column(Boolean, nullable=False, default=False)

    run_at = Column(DateTime, default=datetime.now, index=True)
    completed_at = Column(DateTime, index=True)

    processed = Column(Integer, default=0)
    saved = Column(Integer, default=0)
    completed = Column(Integer, default=0)
    insufficient = Column(Integer, default=0)
    errors = Column(Integer, default=0)
    candidate_count = Column(Integer, default=0)

    result_count = Column(Integer, default=0)
    no_result_reason = Column(String(64))
    no_result_message = Column(Text)
    status = Column(String(16), nullable=False, default='completed', index=True)

    total_evaluations = Column(Integer, default=0)
    completed_count = Column(Integer, default=0)
    insufficient_count = Column(Integer, default=0)
    long_count = Column(Integer, default=0)
    cash_count = Column(Integer, default=0)
    win_count = Column(Integer, default=0)
    loss_count = Column(Integer, default=0)
    neutral_count = Column(Integer, default=0)
    win_rate_pct = Column(Float)
    avg_stock_return_pct = Column(Float)
    avg_simulated_return_pct = Column(Float)
    direction_accuracy_pct = Column(Float)
    summary_json = Column(Text)

    __table_args__ = (
        Index('ix_backtest_run_owner_time', 'owner_id', 'run_at'),
        Index('ix_backtest_run_code_time', 'code', 'run_at'),
    )


class RuleBacktestRun(Base):
    """Persisted AI-assisted rule backtest run."""

    __tablename__ = 'rule_backtest_runs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(String(64), ForeignKey('app_users.id'), index=True, default=BOOTSTRAP_ADMIN_USER_ID)
    code = Column(String(16), nullable=False, index=True)
    strategy_text = Column(Text, nullable=False)
    parsed_strategy_json = Column(Text, nullable=False)
    strategy_hash = Column(String(64), nullable=False, index=True)

    timeframe = Column(String(16), nullable=False, default='daily')
    lookback_bars = Column(Integer, nullable=False, default=252)
    initial_capital = Column(Float, nullable=False, default=100000.0)
    fee_bps = Column(Float, nullable=False, default=0.0)

    parsed_confidence = Column(Float)
    needs_confirmation = Column(Boolean, nullable=False, default=False)
    warnings_json = Column(Text)

    run_at = Column(DateTime, default=datetime.now, index=True)
    completed_at = Column(DateTime, index=True)
    status = Column(String(16), nullable=False, default='completed', index=True)
    no_result_reason = Column(String(64))
    no_result_message = Column(Text)

    trade_count = Column(Integer, default=0)
    win_count = Column(Integer, default=0)
    loss_count = Column(Integer, default=0)
    total_return_pct = Column(Float)
    win_rate_pct = Column(Float)
    avg_trade_return_pct = Column(Float)
    max_drawdown_pct = Column(Float)
    avg_holding_days = Column(Float)
    final_equity = Column(Float)

    summary_json = Column(Text)
    ai_summary = Column(Text)
    equity_curve_json = Column(Text)

    __table_args__ = (
        Index('ix_rule_backtest_owner_time', 'owner_id', 'run_at'),
        Index('ix_rule_backtest_run_code_time', 'code', 'run_at'),
        Index('ix_rule_backtest_run_code_status', 'code', 'status'),
    )


class RuleBacktestTrade(Base):
    """Persisted trade row for a rule backtest run."""

    __tablename__ = 'rule_backtest_trades'

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey('rule_backtest_runs.id'), nullable=False, index=True)
    trade_index = Column(Integer, nullable=False, default=0)
    code = Column(String(16), nullable=False, index=True)

    entry_date = Column(Date, index=True)
    exit_date = Column(Date, index=True)
    entry_price = Column(Float)
    exit_price = Column(Float)
    entry_signal = Column(Text)
    exit_signal = Column(Text)
    return_pct = Column(Float)
    holding_days = Column(Integer)
    entry_rule_json = Column(Text)
    exit_rule_json = Column(Text)
    notes = Column(Text)

    __table_args__ = (
        Index('ix_rule_backtest_trade_run_index', 'run_id', 'trade_index'),
        Index('ix_rule_backtest_trade_code_date', 'code', 'entry_date'),
    )


class RuleBacktestUniverseJob(Base):
    """Persisted local-only universe backtest job metadata."""

    __tablename__ = 'rule_backtest_universe_jobs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(String(64), ForeignKey('app_users.id'), index=True, default=BOOTSTRAP_ADMIN_USER_ID)
    request_label = Column(String(128))
    strategy_text = Column(Text, nullable=False)
    strategy_snapshot_json = Column(Text, nullable=False)
    strategy_hash = Column(String(64), nullable=False, index=True)

    status = Column(String(32), nullable=False, default='queued', index=True)
    symbol_count = Column(Integer, nullable=False, default=0)
    completed_count = Column(Integer, nullable=False, default=0)
    skipped_count = Column(Integer, nullable=False, default=0)
    failed_count = Column(Integer, nullable=False, default=0)
    pending_count = Column(Integer, nullable=False, default=0)
    running_count = Column(Integer, nullable=False, default=0)
    cancel_requested = Column(Boolean, nullable=False, default=False)
    local_data_only = Column(Boolean, nullable=False, default=True)
    execution_mode = Column(String(32), nullable=False, default='preflight_only')

    created_at = Column(DateTime, default=datetime.now, index=True)
    started_at = Column(DateTime)
    completed_at = Column(DateTime, index=True)
    updated_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index('ix_rule_backtest_universe_owner_created', 'owner_id', 'created_at'),
        Index('ix_rule_backtest_universe_status_created', 'status', 'created_at'),
    )


class RuleBacktestUniverseSymbolResult(Base):
    """Compact per-symbol row for a local-only universe backtest job."""

    __tablename__ = 'rule_backtest_universe_symbol_results'

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey('rule_backtest_universe_jobs.id'), nullable=False, index=True)
    owner_id = Column(String(64), ForeignKey('app_users.id'), index=True, default=BOOTSTRAP_ADMIN_USER_ID)
    sequence_index = Column(Integer, nullable=False)
    symbol = Column(String(32), nullable=False, index=True)
    status = Column(String(32), nullable=False, default='pending', index=True)
    reason_code = Column(String(64))
    reason_message = Column(Text)
    runtime_ms = Column(Integer, nullable=False, default=0)
    metrics_json = Column(Text)
    single_run_id = Column(Integer, ForeignKey('rule_backtest_runs.id'), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index('ix_rule_backtest_universe_symbol_sequence', 'job_id', 'sequence_index'),
        Index('ix_rule_backtest_universe_symbol_status', 'job_id', 'status'),
    )


class MarketScannerRun(Base):
    """Persisted market scanner run metadata."""

    __tablename__ = 'market_scanner_runs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(String(64), ForeignKey('app_users.id'), index=True, default=BOOTSTRAP_ADMIN_USER_ID)
    scope = Column(String(16), nullable=False, default=OWNERSHIP_SCOPE_USER, index=True)
    market = Column(String(8), nullable=False, default='cn', index=True)
    profile = Column(String(32), nullable=False, default='cn_preopen_v1', index=True)
    universe_name = Column(String(64), nullable=False)
    status = Column(String(16), nullable=False, default='completed', index=True)

    shortlist_size = Column(Integer, nullable=False, default=5)
    universe_size = Column(Integer, default=0)
    preselected_size = Column(Integer, default=0)
    evaluated_size = Column(Integer, default=0)

    run_at = Column(DateTime, default=datetime.now, index=True)
    completed_at = Column(DateTime, index=True)

    source_summary = Column(String(255))
    summary_json = Column(Text)
    diagnostics_json = Column(Text)
    universe_notes_json = Column(Text)
    scoring_notes_json = Column(Text)

    __table_args__ = (
        Index('ix_market_scanner_run_scope_time', 'scope', 'run_at'),
        Index('ix_market_scanner_run_owner_time', 'owner_id', 'run_at'),
        Index('ix_market_scanner_run_market_time', 'market', 'run_at'),
        Index('ix_market_scanner_run_profile_time', 'profile', 'run_at'),
    )


class MarketScannerCandidate(Base):
    """Persisted shortlisted candidate rows for one market scanner run."""

    __tablename__ = 'market_scanner_candidates'

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey('market_scanner_runs.id'), nullable=False, index=True)
    symbol = Column(String(16), nullable=False, index=True)
    name = Column(String(64))
    rank = Column(Integer, nullable=False, index=True)
    score = Column(Float, nullable=False)
    quality_hint = Column(String(16))
    reason_summary = Column(Text)

    reasons_json = Column(Text)
    key_metrics_json = Column(Text)
    feature_signals_json = Column(Text)
    risk_notes_json = Column(Text)
    watch_context_json = Column(Text)
    boards_json = Column(Text)
    diagnostics_json = Column(Text)

    created_at = Column(DateTime, default=datetime.now, index=True)

    __table_args__ = (
        Index('ix_market_scanner_candidate_run_rank', 'run_id', 'rank'),
        Index('ix_market_scanner_candidate_symbol_created', 'symbol', 'created_at'),
    )


class PortfolioAccount(Base):
    """Portfolio account metadata."""

    __tablename__ = 'portfolio_accounts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(String(64), ForeignKey('app_users.id'), index=True, default=BOOTSTRAP_ADMIN_USER_ID)
    name = Column(String(64), nullable=False)
    broker = Column(String(64))
    market = Column(String(8), nullable=False, default='cn', index=True)  # cn/hk/us
    base_currency = Column(String(8), nullable=False, default='CNY')
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index('ix_portfolio_account_owner_active', 'owner_id', 'is_active'),
    )


class PortfolioBrokerConnection(Base):
    """User-owned broker connection metadata for file import and future read-only sync."""

    __tablename__ = 'portfolio_broker_connections'

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(String(64), ForeignKey('app_users.id'), index=True, default=BOOTSTRAP_ADMIN_USER_ID)
    portfolio_account_id = Column(Integer, ForeignKey('portfolio_accounts.id'), nullable=False, index=True)
    broker_type = Column(String(32), nullable=False, index=True)
    broker_name = Column(String(64))
    connection_name = Column(String(64), nullable=False)
    broker_account_ref = Column(String(128), index=True)
    import_mode = Column(String(16), nullable=False, default='file')
    status = Column(String(16), nullable=False, default='active', index=True)
    last_imported_at = Column(DateTime)
    last_import_source = Column(String(32))
    last_import_fingerprint = Column(String(64))
    sync_metadata_json = Column(Text)
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        UniqueConstraint(
            'owner_id',
            'broker_type',
            'broker_account_ref',
            name='uix_portfolio_broker_connection_owner_ref',
        ),
        Index('ix_portfolio_broker_connection_owner_status', 'owner_id', 'status'),
    )


class PortfolioImportOperation(Base):
    """Completed broker import used as the replay and acknowledgement boundary."""

    __tablename__ = 'portfolio_import_operations'

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(String(64), ForeignKey('app_users.id'), nullable=False, index=True)
    portfolio_account_id = Column(
        Integer,
        ForeignKey('portfolio_accounts.id'),
        nullable=False,
        index=True,
    )
    broker_connection_id = Column(
        Integer,
        ForeignKey('portfolio_broker_connections.id'),
        index=True,
    )
    broker_type = Column(String(32), nullable=False)
    file_fingerprint = Column(String(64), nullable=False)
    status = Column(String(16), nullable=False, default='completed')
    trade_inserted_count = Column(Integer, nullable=False, default=0)
    trade_duplicate_count = Column(Integer, nullable=False, default=0)
    cash_inserted_count = Column(Integer, nullable=False, default=0)
    corporate_action_inserted_count = Column(Integer, nullable=False, default=0)
    completed_at = Column(DateTime, nullable=False, default=datetime.now, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)

    __table_args__ = (
        UniqueConstraint(
            'owner_id',
            'portfolio_account_id',
            'broker_type',
            'file_fingerprint',
            name='uix_portfolio_import_operation_fingerprint',
        ),
        Index(
            'ix_portfolio_import_operation_account_completed',
            'portfolio_account_id',
            'completed_at',
        ),
    )


class PortfolioBrokerSyncState(Base):
    """Current read-only broker sync snapshot kept separate from ledger source events."""

    __tablename__ = 'portfolio_broker_sync_states'

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(String(64), ForeignKey('app_users.id'), index=True, default=BOOTSTRAP_ADMIN_USER_ID)
    broker_connection_id = Column(Integer, ForeignKey('portfolio_broker_connections.id'), nullable=False, index=True)
    portfolio_account_id = Column(Integer, ForeignKey('portfolio_accounts.id'), nullable=False, index=True)
    broker_type = Column(String(32), nullable=False, index=True)
    broker_account_ref = Column(String(128), index=True)
    sync_source = Column(String(32), nullable=False, default='api', index=True)
    sync_status = Column(String(16), nullable=False, default='success', index=True)
    snapshot_date = Column(Date, nullable=False, index=True)
    synced_at = Column(DateTime, nullable=False, default=datetime.now, index=True)
    base_currency = Column(String(8), nullable=False, default='USD')
    total_cash = Column(Float, nullable=False, default=0.0)
    total_market_value = Column(Float, nullable=False, default=0.0)
    total_equity = Column(Float, nullable=False, default=0.0)
    realized_pnl = Column(Float, nullable=False, default=0.0)
    unrealized_pnl = Column(Float, nullable=False, default=0.0)
    fx_stale = Column(Boolean, nullable=False, default=False)
    payload_json = Column(Text)
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        UniqueConstraint('broker_connection_id', name='uix_portfolio_broker_sync_connection'),
        Index('ix_portfolio_broker_sync_owner_account_time', 'owner_id', 'portfolio_account_id', 'synced_at'),
    )


class PortfolioBrokerSyncPosition(Base):
    """Current synced positions for one broker connection."""

    __tablename__ = 'portfolio_broker_sync_positions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(String(64), ForeignKey('app_users.id'), index=True, default=BOOTSTRAP_ADMIN_USER_ID)
    broker_connection_id = Column(Integer, ForeignKey('portfolio_broker_connections.id'), nullable=False, index=True)
    portfolio_account_id = Column(Integer, ForeignKey('portfolio_accounts.id'), nullable=False, index=True)
    broker_position_ref = Column(String(64), index=True)
    symbol = Column(String(16), nullable=False, index=True)
    market = Column(String(8), nullable=False, default='us')
    currency = Column(String(8), nullable=False, default='USD')
    quantity = Column(Float, nullable=False, default=0.0)
    avg_cost = Column(Float, nullable=False, default=0.0)
    last_price = Column(Float, nullable=False, default=0.0)
    market_value_base = Column(Float, nullable=False, default=0.0)
    unrealized_pnl_base = Column(Float, nullable=False, default=0.0)
    valuation_currency = Column(String(8), nullable=False, default='USD')
    payload_json = Column(Text)
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        UniqueConstraint(
            'broker_connection_id',
            'symbol',
            'market',
            'currency',
            name='uix_portfolio_broker_sync_position_key',
        ),
        Index('ix_portfolio_broker_sync_position_owner_account', 'owner_id', 'portfolio_account_id'),
    )


class PortfolioBrokerSyncCashBalance(Base):
    """Current synced cash balances for one broker connection."""

    __tablename__ = 'portfolio_broker_sync_cash_balances'

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(String(64), ForeignKey('app_users.id'), index=True, default=BOOTSTRAP_ADMIN_USER_ID)
    broker_connection_id = Column(Integer, ForeignKey('portfolio_broker_connections.id'), nullable=False, index=True)
    portfolio_account_id = Column(Integer, ForeignKey('portfolio_accounts.id'), nullable=False, index=True)
    currency = Column(String(8), nullable=False, default='USD')
    amount = Column(Float, nullable=False, default=0.0)
    amount_base = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        UniqueConstraint(
            'broker_connection_id',
            'currency',
            name='uix_portfolio_broker_sync_cash_key',
        ),
        Index('ix_portfolio_broker_sync_cash_owner_account', 'owner_id', 'portfolio_account_id'),
    )


class PortfolioTrade(Base):
    """Executed trade events used as the source of truth for replay."""

    __tablename__ = 'portfolio_trades'

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey('portfolio_accounts.id'), nullable=False, index=True)
    trade_uid = Column(String(128))
    symbol = Column(String(16), nullable=False, index=True)
    market = Column(String(8), nullable=False, default='cn')
    currency = Column(String(8), nullable=False, default='CNY')
    trade_date = Column(Date, nullable=False, index=True)
    side = Column(String(8), nullable=False)  # buy/sell
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    fee = Column(Float, default=0.0)
    tax = Column(Float, default=0.0)
    note = Column(String(255))
    dedup_hash = Column(String(64), index=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    voided_at = Column(DateTime, index=True)
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        UniqueConstraint('account_id', 'trade_uid', name='uix_portfolio_trade_uid'),
        UniqueConstraint('account_id', 'dedup_hash', name='uix_portfolio_trade_dedup_hash'),
        Index('ix_portfolio_trade_account_date', 'account_id', 'trade_date'),
        Index('ix_portfolio_trade_account_active_date', 'account_id', 'is_active', 'trade_date'),
    )


class PortfolioCashLedger(Base):
    """Cash in/out events."""

    __tablename__ = 'portfolio_cash_ledger'

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey('portfolio_accounts.id'), nullable=False, index=True)
    event_date = Column(Date, nullable=False, index=True)
    direction = Column(String(8), nullable=False)  # in/out
    amount = Column(Float, nullable=False)
    currency = Column(String(8), nullable=False, default='CNY')
    note = Column(String(255))
    created_at = Column(DateTime, default=datetime.now, index=True)

    __table_args__ = (
        Index('ix_portfolio_cash_account_date', 'account_id', 'event_date'),
    )


class PortfolioCorporateAction(Base):
    """Corporate actions that impact cash or share quantity."""

    __tablename__ = 'portfolio_corporate_actions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey('portfolio_accounts.id'), nullable=False, index=True)
    symbol = Column(String(16), nullable=False, index=True)
    market = Column(String(8), nullable=False, default='cn')
    currency = Column(String(8), nullable=False, default='CNY')
    effective_date = Column(Date, nullable=False, index=True)
    action_type = Column(String(24), nullable=False)  # cash_dividend/split_adjustment
    cash_dividend_per_share = Column(Float)
    split_ratio = Column(Float)
    note = Column(String(255))
    created_at = Column(DateTime, default=datetime.now, index=True)

    __table_args__ = (
        Index('ix_portfolio_ca_account_date', 'account_id', 'effective_date'),
    )


class PortfolioPosition(Base):
    """Latest replayed position snapshot for each symbol in one account."""

    __tablename__ = 'portfolio_positions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey('portfolio_accounts.id'), nullable=False, index=True)
    cost_method = Column(String(8), nullable=False, default='fifo')
    symbol = Column(String(16), nullable=False, index=True)
    market = Column(String(8), nullable=False, default='cn')
    currency = Column(String(8), nullable=False, default='CNY')
    quantity = Column(Float, nullable=False, default=0.0)
    avg_cost = Column(Float, nullable=False, default=0.0)
    total_cost = Column(Float, nullable=False, default=0.0)
    last_price = Column(Float, nullable=False, default=0.0)
    market_value_base = Column(Float, nullable=False, default=0.0)
    unrealized_pnl_base = Column(Float, nullable=False, default=0.0)
    valuation_currency = Column(String(8), nullable=False, default='CNY')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, index=True)

    __table_args__ = (
        UniqueConstraint(
            'account_id',
            'symbol',
            'market',
            'currency',
            'cost_method',
            name='uix_portfolio_position_account_symbol_market_currency',
        ),
    )


class PortfolioPositionLot(Base):
    """Lot-level remaining quantities used by FIFO replay."""

    __tablename__ = 'portfolio_position_lots'

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey('portfolio_accounts.id'), nullable=False, index=True)
    cost_method = Column(String(8), nullable=False, default='fifo')
    symbol = Column(String(16), nullable=False, index=True)
    market = Column(String(8), nullable=False, default='cn')
    currency = Column(String(8), nullable=False, default='CNY')
    open_date = Column(Date, nullable=False, index=True)
    remaining_quantity = Column(Float, nullable=False, default=0.0)
    unit_cost = Column(Float, nullable=False, default=0.0)
    source_trade_id = Column(Integer, ForeignKey('portfolio_trades.id'))
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, index=True)

    __table_args__ = (
        Index('ix_portfolio_lot_account_symbol', 'account_id', 'symbol'),
    )


class PortfolioDailySnapshot(Base):
    """Daily account snapshot generated by read-time replay."""

    __tablename__ = 'portfolio_daily_snapshots'

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey('portfolio_accounts.id'), nullable=False, index=True)
    snapshot_date = Column(Date, nullable=False, index=True)
    cost_method = Column(String(8), nullable=False, default='fifo')  # fifo/avg
    base_currency = Column(String(8), nullable=False, default='CNY')
    total_cash = Column(Float, nullable=False, default=0.0)
    total_market_value = Column(Float, nullable=False, default=0.0)
    total_equity = Column(Float, nullable=False, default=0.0)
    unrealized_pnl = Column(Float, nullable=False, default=0.0)
    realized_pnl = Column(Float, nullable=False, default=0.0)
    fee_total = Column(Float, nullable=False, default=0.0)
    tax_total = Column(Float, nullable=False, default=0.0)
    fx_stale = Column(Boolean, nullable=False, default=False)
    payload = Column(Text)
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        UniqueConstraint(
            'account_id',
            'snapshot_date',
            'cost_method',
            name='uix_portfolio_snapshot_account_date_method',
        ),
    )


class PortfolioFxRate(Base):
    """Cached FX rates used for cross-currency portfolio conversion."""

    __tablename__ = 'portfolio_fx_rates'

    id = Column(Integer, primary_key=True, autoincrement=True)
    from_currency = Column(String(8), nullable=False, index=True)
    to_currency = Column(String(8), nullable=False, index=True)
    rate_date = Column(Date, nullable=False, index=True)
    rate = Column(Float, nullable=False)
    source = Column(String(32), nullable=False, default='manual')
    is_stale = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        UniqueConstraint(
            'from_currency',
            'to_currency',
            'rate_date',
            name='uix_portfolio_fx_pair_date',
        ),
    )


class UserWatchlistItem(Base):
    """User-owned tracked candidate entry used by scanner actions."""

    __tablename__ = 'user_watchlist_items'

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(String(64), ForeignKey('app_users.id'), nullable=False, index=True, default=BOOTSTRAP_ADMIN_USER_ID)
    symbol = Column(String(16), nullable=False, index=True)
    market = Column(String(8), nullable=False, default='cn', index=True)
    name = Column(String(128))
    source = Column(String(32), nullable=False, default='scanner', index=True)
    scanner_run_id = Column(Integer, index=True)
    scanner_rank = Column(Integer)
    scanner_score = Column(Float)
    last_scored_at = Column(DateTime, index=True)
    score_source = Column(String(32))
    score_profile = Column(String(64))
    score_reason = Column(Text)
    score_status = Column(String(16), default='stale', index=True)
    score_error = Column(Text)
    theme_id = Column(String(64), index=True)
    universe_type = Column(String(32), index=True)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, index=True)

    __table_args__ = (
        UniqueConstraint('owner_id', 'symbol', 'market', name='uix_user_watchlist_owner_symbol_market'),
        Index('ix_user_watchlist_owner_updated', 'owner_id', 'updated_at'),
    )


class UserAlertRule(Base):
    """Owner-scoped in-app alert rule contract."""

    __tablename__ = 'user_alert_rules'

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(String(64), ForeignKey('app_users.id'), nullable=False, index=True)
    rule_type = Column(String(48), nullable=False, default='watchlist_price_threshold', index=True)
    symbol = Column(String(16), nullable=False, index=True)
    direction = Column(String(8), nullable=False, index=True)
    threshold_price = Column(Numeric(18, 6), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    note = Column(Text)
    delivery_mode = Column(String(16), nullable=False, default='in_app', index=True)
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, index=True)

    __table_args__ = (
        Index('ix_user_alert_rule_owner_enabled_symbol', 'owner_id', 'enabled', 'symbol'),
        Index('ix_user_alert_rule_owner_updated', 'owner_id', 'updated_at'),
    )


class UserAlertEvent(Base):
    """Sanitized owner-scoped in-app alert event contract."""

    __tablename__ = 'user_alert_events'

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(String(64), ForeignKey('app_users.id'), nullable=False, index=True)
    rule_id = Column(Integer, ForeignKey('user_alert_rules.id'), index=True)
    event_type = Column(String(64), nullable=False, default='watchlist_price_threshold', index=True)
    symbol = Column(String(16), index=True)
    direction = Column(String(8), index=True)
    threshold_price = Column(Numeric(18, 6))
    title = Column(String(160), nullable=False)
    message = Column(Text)
    delivery_mode = Column(String(16), nullable=False, default='in_app', index=True)
    read_at = Column(DateTime, index=True)
    created_at = Column(DateTime, default=datetime.now, index=True)

    __table_args__ = (
        Index('ix_user_alert_event_owner_time', 'owner_id', 'created_at'),
        Index('ix_user_alert_event_owner_rule_time', 'owner_id', 'rule_id', 'created_at'),
    )


class ConversationMessage(Base):
    """
    Agent 对话历史记录表
    """
    __tablename__ = 'conversation_messages'

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), index=True, nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.now, index=True)


class ConversationSessionRecord(Base):
    """First-class chat session ownership row for user-scoped conversation history."""

    __tablename__ = 'conversation_sessions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), nullable=False, unique=True, index=True)
    owner_id = Column(String(64), ForeignKey('app_users.id'), index=True, default=BOOTSTRAP_ADMIN_USER_ID)
    title = Column(String(255))
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, index=True)

    __table_args__ = (
        Index('ix_conversation_session_owner_updated', 'owner_id', 'updated_at'),
    )


class LLMUsage(Base):
    """One row per litellm.completion() call — token-usage audit log."""

    __tablename__ = 'llm_usage'

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 'analysis' | 'agent' | 'market_review'
    call_type = Column(String(32), nullable=False, index=True)
    model = Column(String(128), nullable=False)
    stock_code = Column(String(16), nullable=True)
    prompt_tokens = Column(Integer, nullable=False, default=0)
    completion_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    called_at = Column(DateTime, default=datetime.now, index=True)


class DatabaseManager:
    """
    数据库管理器 - 单例模式
    
    职责：
    1. 管理数据库连接池
    2. 提供 Session 上下文管理
    3. 封装数据存取操作
    """
    
    _instance: Optional['DatabaseManager'] = None
    _initialized: bool = False

    def _prime_runtime_state_defaults(self) -> None:
        """Seed phase/store flags before any initialization step can fail."""
        self._phase_a_store = None
        self._phase_a_enabled = False
        self._phase_b_store = None
        self._phase_b_enabled = False
        self._phase_c_store = None
        self._phase_c_enabled = False
        self._phase_d_store = None
        self._phase_d_enabled = False
        self._phase_e_store = None
        self._phase_e_enabled = False
        self._phase_f_store = None
        self._phase_f_enabled = False
        self._phase_g_store = None
        self._phase_g_enabled = False
        self._postgres_bridge_url = None
        self._postgres_bridge_auto_apply_schema = True
    
    def __new__(cls, *args, **kwargs):
        """单例模式实现"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
            cls._instance._prime_runtime_state_defaults()
        return cls._instance
    
    def __init__(self, db_url: Optional[str] = None):
        """
        初始化数据库管理器
        
        Args:
            db_url: 数据库连接 URL（可选，默认从配置读取）
        """
        if getattr(self, '_initialized', False):
            return

        self._prime_runtime_state_defaults()
        try:
            if db_url is None:
                config = get_config()
                db_url = config.get_db_url()
            else:
                config = get_config()

            # 创建数据库引擎
            self._engine = create_engine(
                db_url,
                echo=False,  # 设为 True 可查看 SQL 语句
                pool_pre_ping=True,  # 连接健康检查
            )

            # 创建 Session 工厂
            self._SessionLocal = sessionmaker(
                bind=self._engine,
                autocommit=False,
                autoflush=False,
            )

            # 创建所有表
            Base.metadata.create_all(self._engine)
            self._run_multi_user_migrations()
            self._postgres_bridge_url = str(getattr(config, "postgres_phase_a_url", "") or "").strip() or None
            self._postgres_bridge_auto_apply_schema = bool(
                getattr(config, "postgres_phase_a_apply_schema", True)
            )
            if self._postgres_bridge_url:
                try:
                    storage_postgres_bridge.initialize_postgres_phase_stores(
                        self,
                        bridge_url=self._postgres_bridge_url,
                        auto_apply_schema=self._postgres_bridge_auto_apply_schema,
                    )
                except Exception as exc:
                    self._dispose_postgres_phase_stores()
                    raise RuntimeError(
                        storage_postgres_bridge.format_bridge_initialization_error(
                            failed_phase=getattr(exc, "failed_phase", None),
                            initialized_phases=getattr(exc, "initialized_phases", ()),
                        )
                    ) from exc

            self._initialized = True
            logger.info("数据库初始化完成: %s", _redact_db_url_for_log(db_url))
            topology = self.describe_database_topology()
            enabled_store_names = [
                phase_key
                for phase_key, phase_state in topology["stores"].items()
                if phase_state.get("enabled")
            ]
            logger.info(
                "数据库拓扑: primary=%s postgres_bridge=%s enabled_stores=%s phase_f_mode=%s phase_g_mode=%s",
                topology["primary_runtime"],
                topology["postgres_bridge"]["enabled"],
                ",".join(enabled_store_names) if enabled_store_names else "none",
                topology["stores"]["phase_f"]["mode"],
                topology["stores"]["phase_g"]["mode"],
            )
            if topology["postgres_bridge"]["enabled"]:
                logger.info(
                    "PostgreSQL store 初始化状态: %s",
                    json.dumps(
                        {
                            phase_key: {
                                "mode": phase_state["mode"],
                                "last_apply_status": phase_state["schema"]["last_apply_status"],
                                "bootstrap_recorded": phase_state["schema"]["bootstrap_recorded"],
                            }
                            for phase_key, phase_state in topology["stores"].items()
                            if phase_state.get("enabled")
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                )
            logger.debug(
                "数据库拓扑详情: %s",
                json.dumps(_sanitize_database_topology_for_log(topology), ensure_ascii=False, sort_keys=True),
            )

            # 注册退出钩子，确保程序退出时关闭数据库连接
            atexit.register(DatabaseManager._cleanup_engine, self._engine)
        except Exception:
            self._initialized = False
            self._dispose_postgres_phase_stores()
            engine = getattr(self, "_engine", None)
            if engine is not None:
                try:
                    engine.dispose()
                except Exception as cleanup_exc:
                    logger.warning("初始化失败后清理数据库引擎时出错: %s", cleanup_exc)
                finally:
                    delattr(self, "_engine")
            if hasattr(self, "_SessionLocal"):
                delattr(self, "_SessionLocal")
            type(self)._instance = None
            raise
    
    @classmethod
    def get_instance(cls) -> 'DatabaseManager':
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset_instance(cls) -> None:
        """重置单例（用于测试）"""
        if cls._instance is not None:
            cls._instance._dispose_postgres_phase_stores()
            if hasattr(cls._instance, '_engine') and cls._instance._engine is not None:
                cls._instance._engine.dispose()
            cls._instance._initialized = False
            cls._instance = None

    def _dispose_postgres_phase_stores(self) -> None:
        storage_postgres_bridge.dispose_postgres_phase_stores(self)

    def describe_database_topology(self, *, include_connection_probe: bool = False) -> Dict[str, Any]:
        return storage_topology_report.build_database_topology_report(
            self,
            config=get_config(),
            include_connection_probe=include_connection_probe,
        )

    @classmethod
    def _cleanup_engine(cls, engine) -> None:
        """
        清理数据库引擎（atexit 钩子）

        确保程序退出时关闭所有数据库连接，避免 ResourceWarning

        Args:
            engine: SQLAlchemy 引擎对象
        """
        try:
            if engine is not None:
                engine.dispose()
                logger.debug("数据库引擎已清理")
        except Exception as e:
            logger.warning(f"清理数据库引擎时出错: {e}")
    
    def get_session(self) -> Session:
        """
        获取数据库 Session
        
        使用示例:
            with db.get_session() as session:
                # 执行查询
                session.commit()  # 如果需要
        """
        if not getattr(self, '_initialized', False) or not hasattr(self, '_SessionLocal'):
            raise RuntimeError(
                "DatabaseManager 未正确初始化。"
                "请确保通过 DatabaseManager.get_instance() 获取实例。"
            )
        session = self._SessionLocal()
        try:
            return session
        except Exception:
            session.close()
            raise

    @contextmanager
    def session_scope(self):
        """Provide a transactional scope around a series of operations."""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @staticmethod
    def _parse_optional_datetime(value: Any) -> Optional[datetime]:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception:
            return None

    @staticmethod
    def _market_overview_snapshot_payload(row: MarketOverviewSnapshot) -> Dict[str, Any]:
        payload = DatabaseManager._safe_json_loads(getattr(row, "payload_json", None), {})
        if not isinstance(payload, dict):
            payload = {}
        return {
            "key": row.key,
            "payload": payload,
            "as_of": row.as_of.isoformat(timespec="seconds") if row.as_of else None,
            "updated_at": row.updated_at.isoformat(timespec="seconds") if row.updated_at else None,
            "source": row.source,
            "freshness": row.freshness,
            "is_fallback": bool(row.is_fallback),
            "error_count": int(row.error_count or 0),
            "last_error": row.last_error,
            "last_error_at": row.last_error_at.isoformat(timespec="seconds") if row.last_error_at else None,
        }

    def get_market_overview_snapshot(self, key: str) -> Optional[Dict[str, Any]]:
        normalized_key = str(key or "").strip()
        if not normalized_key:
            return None
        with self.get_session() as session:
            row = session.get(MarketOverviewSnapshot, normalized_key)
            if row is None:
                return None
            return self._market_overview_snapshot_payload(row)

    def save_market_overview_snapshot(self, *, key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        normalized_key = str(key or "").strip()
        if not normalized_key:
            raise ValueError("market overview snapshot key is required")
        payload_dict = dict(payload or {})
        now = datetime.now()
        freshness_evidence = payload_dict.get("sourceFreshnessEvidence")
        evidence_as_of = (
            freshness_evidence.get("asOf")
            if isinstance(freshness_evidence, dict)
            else None
        )
        as_of = self._parse_optional_datetime(
            payload_dict.get("asOf")
            or payload_dict.get("as_of")
            or evidence_as_of
        )
        source = str(payload_dict.get("source") or "")[:64] or None
        freshness = str(payload_dict.get("freshness") or "")[:32] or None
        is_fallback = bool(payload_dict.get("isFallback") or payload_dict.get("fallbackUsed") or payload_dict.get("fallback_used"))
        with self.session_scope() as session:
            row = session.get(MarketOverviewSnapshot, normalized_key)
            if row is None:
                row = MarketOverviewSnapshot(key=normalized_key)
                session.add(row)
            row.payload_json = self._safe_json_dumps(payload_dict)
            row.as_of = as_of
            row.updated_at = now
            row.source = source
            row.freshness = freshness
            row.is_fallback = is_fallback
            row.last_error = None
            row.last_error_at = None
            session.flush()
            return self._market_overview_snapshot_payload(row)

    def record_market_overview_snapshot_error(self, *, key: str, error: str) -> None:
        normalized_key = str(key or "").strip()
        if not normalized_key:
            return
        concise_error = str(error or "").strip()[:180]
        if not concise_error:
            return
        with self.session_scope() as session:
            row = session.get(MarketOverviewSnapshot, normalized_key)
            if row is None:
                return
            row.error_count = int(row.error_count or 0) + 1
            row.last_error = concise_error
            row.last_error_at = datetime.now()

    def _run_multi_user_migrations(self) -> None:
        """Apply lightweight SQLite-safe schema migrations for Phase 1 ownership."""
        bootstrap_user_id = BOOTSTRAP_ADMIN_USER_ID
        with self._engine.begin() as conn:
            self._ensure_bootstrap_admin_user_row(conn)
            self._seed_admin_rbac_compatibility_rows(conn)

            self._add_column_if_missing(conn, "analysis_history", "owner_id", "VARCHAR(64)")
            self._add_column_if_missing(conn, "analysis_history", "is_test", "BOOLEAN NOT NULL DEFAULT 0")
            self._add_column_if_missing(conn, "backtest_results", "owner_id", "VARCHAR(64)")
            self._add_column_if_missing(conn, "backtest_runs", "owner_id", "VARCHAR(64)")
            self._add_column_if_missing(conn, "rule_backtest_runs", "owner_id", "VARCHAR(64)")
            self._add_column_if_missing(conn, "rule_backtest_universe_jobs", "owner_id", "VARCHAR(64)")
            self._add_column_if_missing(conn, "rule_backtest_universe_symbol_results", "owner_id", "VARCHAR(64)")
            self._add_column_if_missing(conn, "market_scanner_runs", "owner_id", "VARCHAR(64)")
            self._add_column_if_missing(conn, "portfolio_trades", "is_active", "BOOLEAN NOT NULL DEFAULT 1")
            self._add_column_if_missing(conn, "portfolio_trades", "voided_at", "DATETIME")
            self._add_column_if_missing(conn, "portfolio_trades", "updated_at", "DATETIME")
            self._add_column_if_missing(conn, "user_watchlist_items", "last_scored_at", "DATETIME")
            self._add_column_if_missing(conn, "user_watchlist_items", "score_source", "VARCHAR(32)")
            self._add_column_if_missing(conn, "user_watchlist_items", "score_profile", "VARCHAR(64)")
            self._add_column_if_missing(conn, "user_watchlist_items", "score_reason", "TEXT")
            self._add_column_if_missing(conn, "user_watchlist_items", "score_status", "VARCHAR(16) DEFAULT 'stale'")
            self._add_column_if_missing(conn, "user_watchlist_items", "score_error", "TEXT")
            self._add_column_if_missing(conn, "durable_task_states", "attempt_count", "INTEGER NOT NULL DEFAULT 0")
            self._add_column_if_missing(conn, "durable_task_states", "max_attempts", "INTEGER NOT NULL DEFAULT 1")
            self._add_column_if_missing(conn, "durable_task_states", "lease_owner", "VARCHAR(128)")
            self._add_column_if_missing(conn, "durable_task_states", "lease_expires_at", "DATETIME")
            self._add_column_if_missing(conn, "durable_task_states", "active_dedupe_key_hash", "VARCHAR(128)")
            self._add_column_if_missing(conn, "quota_policy_definitions", "provider", "VARCHAR(64)")
            self._add_column_if_missing(conn, "quota_policy_definitions", "model_tier", "VARCHAR(64)")
            self._add_column_if_missing(conn, "quota_policy_definitions", "daily_budget_units", "INTEGER")
            self._add_column_if_missing(conn, "quota_policy_definitions", "monthly_budget_units", "INTEGER")
            self._add_column_if_missing(conn, "quota_policy_definitions", "token_cap", "INTEGER")
            self._add_column_if_missing(conn, "quota_policy_definitions", "request_cap", "INTEGER")
            self._add_column_if_missing(conn, "quota_policy_definitions", "enabled", "BOOLEAN NOT NULL DEFAULT 1")
            self._add_column_if_missing(conn, "quota_policy_definitions", "metadata_json", "TEXT")
            self._add_column_if_missing(conn, "quota_usage_windows", "provider", "VARCHAR(64)")
            self._add_column_if_missing(conn, "quota_usage_windows", "model_tier", "VARCHAR(64)")
            self._add_column_if_missing(conn, "quota_usage_windows", "window_identity_key", "VARCHAR(512) NOT NULL DEFAULT ''")
            self._add_column_if_missing(conn, "quota_usage_windows", "reserved_units", "INTEGER NOT NULL DEFAULT 0")
            self._add_column_if_missing(conn, "quota_usage_windows", "consumed_units", "INTEGER NOT NULL DEFAULT 0")
            self._add_column_if_missing(conn, "quota_usage_windows", "request_count", "INTEGER NOT NULL DEFAULT 0")
            self._add_column_if_missing(conn, "quota_reservations", "provider", "VARCHAR(64)")
            self._add_column_if_missing(conn, "quota_reservations", "model_tier", "VARCHAR(64)")
            self._add_column_if_missing(conn, "quota_reservations", "request_idempotency_key_hash", "VARCHAR(128)")
            self._add_column_if_missing(conn, "quota_reservations", "reason_code", "VARCHAR(64)")
            self._add_column_if_missing(conn, "quota_reservations", "metadata_json", "TEXT")
            # Backfill logical quota identities before creating the unique index.
            # Existing rows get the new column default first; indexing that default
            # would report false duplicates and skip the non-destructive backfill.
            self._backfill_quota_usage_window_identity_keys(conn)
            self._add_column_if_missing(conn, "model_pricing_policies", "source_label", "VARCHAR(128)")
            self._add_column_if_missing(conn, "model_pricing_policies", "source_url", "VARCHAR(500)")
            self._add_column_if_missing(conn, "model_pricing_policies", "metadata_json", "TEXT")
            self._add_column_if_missing(conn, "llm_cost_ledger", "owner_user_id", "VARCHAR(64)")
            self._add_column_if_missing(conn, "llm_cost_ledger", "guest_bucket_hash", "VARCHAR(128)")
            self._add_column_if_missing(conn, "llm_cost_ledger", "route_family", "VARCHAR(64)")
            self._add_column_if_missing(conn, "llm_cost_ledger", "cached_input_tokens", "INTEGER NOT NULL DEFAULT 0")
            self._add_column_if_missing(conn, "llm_cost_ledger", "cache_miss_input_tokens", "INTEGER NOT NULL DEFAULT 0")
            self._add_column_if_missing(conn, "llm_cost_ledger", "quota_reservation_id", "VARCHAR(64)")
            self._add_column_if_missing(conn, "llm_cost_ledger", "request_hash", "VARCHAR(128)")
            self._add_column_if_missing(conn, "llm_cost_ledger", "status", "VARCHAR(32) NOT NULL DEFAULT 'ok'")
            self._add_column_if_missing(conn, "llm_cost_ledger", "metadata_json", "TEXT")
            self._add_column_if_missing(conn, "app_users", "mfa_enabled", "BOOLEAN NOT NULL DEFAULT 0")
            self._add_column_if_missing(conn, "app_users", "mfa_secret_ref", "TEXT")
            self._add_column_if_missing(conn, "app_users", "mfa_recovery_codes_hash", "TEXT")
            self._add_column_if_missing(conn, "app_users", "mfa_created_at", "DATETIME")
            self._add_column_if_missing(conn, "app_users", "mfa_enabled_at", "DATETIME")
            self._add_column_if_missing(conn, "app_users", "mfa_last_verified_at", "DATETIME")
            self._add_column_if_missing(
                conn,
                "market_scanner_runs",
                "scope",
                f"VARCHAR(16) NOT NULL DEFAULT '{OWNERSHIP_SCOPE_USER}'",
            )

            self._create_index_if_missing(
                conn,
                "ix_app_user_session_user_expiry",
                "app_user_sessions",
                "user_id, expires_at",
            )
            self._create_index_if_missing(
                conn,
                "ix_app_user_session_user_revoked_expiry",
                "app_user_sessions",
                "user_id, revoked_at, expires_at",
            )
            self._create_index_if_missing(
                conn,
                "ix_auth_rate_limit_type_expiry",
                "auth_rate_limit_buckets",
                "bucket_type, expires_at",
            )
            self._create_index_if_missing(
                conn,
                "ix_analysis_owner_created",
                "analysis_history",
                "owner_id, created_at",
            )
            self._create_index_if_missing(
                conn,
                "ix_analysis_owner_query",
                "analysis_history",
                "owner_id, query_id",
            )
            self._create_index_if_missing(
                conn,
                "ix_analysis_history_is_test_created",
                "analysis_history",
                "is_test, created_at",
            )
            self._create_index_if_missing(
                conn,
                "ix_backtest_result_owner_evaluated",
                "backtest_results",
                "owner_id, evaluated_at",
            )
            self._create_index_if_missing(
                conn,
                "ix_backtest_run_owner_time",
                "backtest_runs",
                "owner_id, run_at",
            )
            self._create_index_if_missing(
                conn,
                "ix_rule_backtest_owner_time",
                "rule_backtest_runs",
                "owner_id, run_at",
            )
            self._create_index_if_missing(
                conn,
                "ix_rule_backtest_universe_owner_created",
                "rule_backtest_universe_jobs",
                "owner_id, created_at",
            )
            self._create_index_if_missing(
                conn,
                "ix_rule_backtest_universe_status_created",
                "rule_backtest_universe_jobs",
                "status, created_at",
            )
            self._create_index_if_missing(
                conn,
                "ix_rule_backtest_universe_symbol_sequence",
                "rule_backtest_universe_symbol_results",
                "job_id, sequence_index",
            )
            self._create_index_if_missing(
                conn,
                "ix_rule_backtest_universe_symbol_status",
                "rule_backtest_universe_symbol_results",
                "job_id, status",
            )
            self._create_index_if_missing(
                conn,
                "ix_market_scanner_run_scope_time",
                "market_scanner_runs",
                "scope, run_at",
            )
            self._create_index_if_missing(
                conn,
                "ix_market_scanner_run_owner_time",
                "market_scanner_runs",
                "owner_id, run_at",
            )
            self._create_index_if_missing(
                conn,
                "ix_portfolio_trade_account_active_date",
                "portfolio_trades",
                "account_id, is_active, trade_date",
            )
            self._create_index_if_missing(
                conn,
                "ix_durable_task_owner_created",
                "durable_task_states",
                "owner_user_id, created_at",
            )
            self._create_index_if_missing(
                conn,
                "ix_durable_task_owner_status_created",
                "durable_task_states",
                "owner_user_id, status, created_at",
            )
            self._create_index_if_missing(
                conn,
                "ix_durable_task_status_updated",
                "durable_task_states",
                "status, updated_at",
            )
            self._create_index_if_missing(
                conn,
                "ix_durable_task_status_lease",
                "durable_task_states",
                "status, lease_expires_at",
            )
            self._create_index_if_missing(
                conn,
                "ix_durable_task_states_idempotency_key_hash",
                "durable_task_states",
                "idempotency_key_hash",
            )
            self._create_index_if_missing(
                conn,
                "ix_durable_task_states_dedupe_key_hash",
                "durable_task_states",
                "dedupe_key_hash",
            )
            self._create_unique_index_if_missing(
                conn,
                "ux_durable_task_active_dedupe",
                "durable_task_states",
                "owner_user_id, task_type, active_dedupe_key_hash",
            )
            self._create_index_if_missing(
                conn,
                "ix_durable_task_progress_task_sequence",
                "durable_task_progress_events",
                "task_id, sequence",
            )
            self._create_index_if_missing(
                conn,
                "ix_durable_task_progress_task_created",
                "durable_task_progress_events",
                "task_id, created_at",
            )
            self._create_index_if_missing(
                conn,
                "ix_durable_task_progress_owner_created",
                "durable_task_progress_events",
                "owner_user_id, created_at",
            )
            self._create_index_if_missing(
                conn,
                "ix_quota_policy_scope_route",
                "quota_policy_definitions",
                "scope_type, route_family",
            )
            self._create_index_if_missing(
                conn,
                "ix_quota_policy_scope_provider",
                "quota_policy_definitions",
                "scope_type, provider, model_tier",
            )
            self._create_index_if_missing(
                conn,
                "ix_quota_window_owner_type_start",
                "quota_usage_windows",
                "owner_user_id, window_type, window_start",
            )
            self._create_index_if_missing(
                conn,
                "ix_quota_window_route_type_start",
                "quota_usage_windows",
                "route_family, window_type, window_start",
            )
            self._create_index_if_missing(
                conn,
                "ix_quota_window_provider_type_start",
                "quota_usage_windows",
                "provider, model_tier, window_type, window_start",
            )
            self._create_unique_index_if_missing(
                conn,
                "ux_quota_window_identity",
                "quota_usage_windows",
                "window_identity_key, window_type, window_start",
            )
            self._create_index_if_missing(
                conn,
                "ix_quota_reservation_owner_status_created",
                "quota_reservations",
                "owner_user_id, status, created_at",
            )
            self._create_index_if_missing(
                conn,
                "ix_quota_reservation_route_status_created",
                "quota_reservations",
                "route_family, status, created_at",
            )
            self._create_index_if_missing(
                conn,
                "ix_quota_reservation_status_expires",
                "quota_reservations",
                "status, expires_at",
            )
            self._create_unique_index_if_missing(
                conn,
                "ux_quota_reservation_request_idempotency",
                "quota_reservations",
                "request_idempotency_key_hash",
            )
            self._create_index_if_missing(
                conn,
                "ix_model_pricing_provider_model_effective",
                "model_pricing_policies",
                "provider, model, active, effective_from, effective_until",
            )
            self._create_index_if_missing(
                conn,
                "ix_model_pricing_active_updated",
                "model_pricing_policies",
                "active, updated_at",
            )
            self._create_index_if_missing(
                conn,
                "ix_llm_cost_ledger_owner_created",
                "llm_cost_ledger",
                "owner_user_id, created_at",
            )
            self._create_index_if_missing(
                conn,
                "ix_llm_cost_ledger_owner_route_created",
                "llm_cost_ledger",
                "owner_user_id, route_family, created_at",
            )
            self._create_index_if_missing(
                conn,
                "ix_llm_cost_ledger_provider_model_created",
                "llm_cost_ledger",
                "provider, model, created_at",
            )
            self._create_index_if_missing(
                conn,
                "ix_llm_cost_ledger_route_created",
                "llm_cost_ledger",
                "route_family, created_at",
            )
            self._create_index_if_missing(
                conn,
                "ix_provider_quota_policy_provider_route",
                "provider_quota_policies",
                "scope_type, provider, provider_category, route_family, enabled",
            )
            self._create_index_if_missing(
                conn,
                "ix_provider_quota_policy_owner_provider",
                "provider_quota_policies",
                "owner_user_id, provider, provider_category, route_family, enabled",
            )
            self._create_index_if_missing(
                conn,
                "ix_provider_quota_window_provider_route",
                "provider_quota_windows",
                "provider, provider_category, route_family, window_start, window_end",
            )
            self._create_index_if_missing(
                conn,
                "ix_provider_quota_window_end",
                "provider_quota_windows",
                "window_end",
            )
            self._create_index_if_missing(
                conn,
                "ix_provider_circuit_state_provider_route",
                "provider_circuit_states",
                "provider, provider_category, route_family, state",
            )
            self._create_index_if_missing(
                conn,
                "ix_provider_circuit_state_provider_status",
                "provider_circuit_states",
                "provider, state, updated_at",
            )
            self._create_index_if_missing(
                conn,
                "ix_provider_circuit_event_provider_time",
                "provider_circuit_events",
                "provider, provider_category, route_family, created_at",
            )
            self._create_index_if_missing(
                conn,
                "ix_provider_circuit_event_to_state_time",
                "provider_circuit_events",
                "to_state, created_at",
            )
            self._create_index_if_missing(
                conn,
                "ix_provider_probe_event_provider_time",
                "provider_probe_events",
                "provider, provider_category, probe_type, created_at",
            )
            self._create_index_if_missing(
                conn,
                "ix_provider_probe_event_result_time",
                "provider_probe_events",
                "result_bucket, created_at",
            )

            self._migrate_backtest_summaries_table(conn, bootstrap_user_id=bootstrap_user_id)

            conn.exec_driver_sql(
                "UPDATE portfolio_accounts SET owner_id = :owner_id "
                "WHERE owner_id IS NULL OR TRIM(owner_id) = ''",
                {"owner_id": bootstrap_user_id},
            )
            conn.exec_driver_sql(
                "UPDATE analysis_history SET owner_id = :owner_id "
                "WHERE owner_id IS NULL OR TRIM(owner_id) = ''",
                {"owner_id": bootstrap_user_id},
            )
            conn.exec_driver_sql(
                "UPDATE backtest_results SET owner_id = :owner_id "
                "WHERE owner_id IS NULL OR TRIM(owner_id) = ''",
                {"owner_id": bootstrap_user_id},
            )
            conn.exec_driver_sql(
                "UPDATE backtest_runs SET owner_id = :owner_id "
                "WHERE owner_id IS NULL OR TRIM(owner_id) = ''",
                {"owner_id": bootstrap_user_id},
            )
            conn.exec_driver_sql(
                "UPDATE rule_backtest_runs SET owner_id = :owner_id "
                "WHERE owner_id IS NULL OR TRIM(owner_id) = ''",
                {"owner_id": bootstrap_user_id},
            )
            conn.exec_driver_sql(
                "UPDATE rule_backtest_universe_jobs SET owner_id = :owner_id "
                "WHERE owner_id IS NULL OR TRIM(owner_id) = ''",
                {"owner_id": bootstrap_user_id},
            )
            conn.exec_driver_sql(
                "UPDATE rule_backtest_universe_symbol_results SET owner_id = :owner_id "
                "WHERE owner_id IS NULL OR TRIM(owner_id) = ''",
                {"owner_id": bootstrap_user_id},
            )
            conn.exec_driver_sql(
                "UPDATE portfolio_trades SET is_active = 1 "
                "WHERE is_active IS NULL"
            )
            conn.exec_driver_sql(
                "UPDATE portfolio_trades SET updated_at = created_at "
                "WHERE updated_at IS NULL"
            )

            self._backfill_market_scanner_ownership(conn, bootstrap_user_id=bootstrap_user_id)
            self._backfill_conversation_sessions(conn, bootstrap_user_id=bootstrap_user_id)

    @staticmethod
    def _quota_identity_component(value: Any, *, lowercase: bool = False, limit: int = 64) -> str:
        text = str(value or "").strip()
        if lowercase:
            text = text.lower()
        return text[:limit] if text else ""

    @classmethod
    def _quota_identity_segment(cls, label: str, value: str) -> str:
        return f"{label}:{len(value)}:{value}"

    @classmethod
    def quota_window_identity_values(
        cls,
        *,
        owner_user_id: Optional[str],
        route_family: Optional[str],
        provider: Optional[str],
        model_tier: Optional[str],
    ) -> Dict[str, str]:
        parts = (
            cls._quota_identity_segment(
                "owner",
                cls._quota_identity_component(owner_user_id),
            ),
            cls._quota_identity_segment(
                "route",
                cls._quota_identity_component(route_family, lowercase=True),
            ),
            cls._quota_identity_segment(
                "provider",
                cls._quota_identity_component(provider, lowercase=True),
            ),
            cls._quota_identity_segment(
                "model",
                cls._quota_identity_component(model_tier, lowercase=True),
            ),
        )
        return {"window_identity_key": "qwin_scope_v1|" + "|".join(parts)}

    @classmethod
    def quota_reservation_idempotency_hash(
        cls,
        *,
        idempotency_key: Optional[str],
        owner_user_id: Optional[str],
        route_family: Optional[str],
        provider: Optional[str],
        model_tier: Optional[str],
    ) -> Optional[str]:
        request_key = str(idempotency_key or "").strip()
        if not request_key:
            return None
        payload = {
            "version": 1,
            "request_key": request_key,
            "scope": cls.quota_window_identity_values(
                owner_user_id=owner_user_id,
                route_family=route_family,
                provider=provider,
                model_tier=model_tier,
            )["window_identity_key"],
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return "qres_req_v1:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _quota_accounting_window_bounds(window_type: str, now: datetime) -> Tuple[datetime, datetime]:
        if window_type == "monthly":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if start.month == 12:
                end = start.replace(year=start.year + 1, month=1)
            else:
                end = start.replace(month=start.month + 1)
            return start, end
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, start + timedelta(days=1)

    def _move_quota_reserved_units_for_terminal_transition(
        self,
        *,
        session: Session,
        row: QuotaReservation,
        consumed_units: int,
        now: datetime,
    ) -> None:
        estimated_units = max(0, int(row.estimated_units or 0))
        owner_identity = self.quota_window_identity_values(
            owner_user_id=row.owner_user_id,
            route_family=row.route_family,
            provider=row.provider,
            model_tier=row.model_tier,
        )
        route_identity = self.quota_window_identity_values(
            owner_user_id=None,
            route_family=row.route_family,
            provider=row.provider,
            model_tier=row.model_tier,
        )
        identity_keys = {
            owner_identity["window_identity_key"],
            route_identity["window_identity_key"],
        }
        created_at = row.created_at or now
        for window_type, window_start in (
            ("daily", self._quota_accounting_window_bounds("daily", created_at)[0]),
            ("monthly", self._quota_accounting_window_bounds("monthly", created_at)[0]),
        ):
            windows_query = select(QuotaUsageWindow).where(
                QuotaUsageWindow.window_identity_key.in_(identity_keys),
                QuotaUsageWindow.window_type == window_type,
                QuotaUsageWindow.window_start == window_start,
            )
            for window in session.execute(windows_query).scalars().all():
                window.reserved_units = max(0, int(window.reserved_units or 0) - estimated_units)
                window.consumed_units = int(window.consumed_units or 0) + max(0, int(consumed_units or 0))
                window.updated_at = now

    def transition_quota_reservation_terminal_cas(
        self,
        *,
        reservation_id: Optional[str],
        terminal_status: str,
        consumed_units: Optional[int] = None,
        reason_code: Optional[str] = None,
        now: Optional[datetime] = None,
        expire_reserved_before: Optional[datetime] = None,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Move one reserved quota reservation to a terminal state using a CAS update."""
        normalized_id = sanitize_message(str(reservation_id or "").strip())[:64]
        requested_status = str(terminal_status or "").strip().lower()
        if requested_status not in {"consumed", "released", "expired"}:
            raise ValueError("terminal_status must be consumed, released, or expired")
        current_time = now or datetime.now()
        if not normalized_id:
            return {
                "transitioned": False,
                "status": "missing",
                "reservation_id": None,
                "reservation": None,
            }
        if session is None:
            with self.session_scope() as scoped_session:
                return self.transition_quota_reservation_terminal_cas(
                    session=scoped_session,
                    reservation_id=normalized_id,
                    terminal_status=requested_status,
                    consumed_units=consumed_units,
                    reason_code=reason_code,
                    now=current_time,
                    expire_reserved_before=expire_reserved_before,
                )

        row = session.execute(
            select(QuotaReservation)
            .where(QuotaReservation.reservation_id == normalized_id)
            .limit(1)
        ).scalar_one_or_none()
        if row is None:
            return {
                "transitioned": False,
                "status": "missing",
                "reservation_id": normalized_id,
                "reservation": None,
            }

        current_status = str(row.status or "").strip().lower()
        if current_status != "reserved":
            return {
                "transitioned": False,
                "status": current_status or "expired",
                "reservation_id": normalized_id,
                "reservation": row.to_dict(),
            }

        target_status = requested_status
        target_reason = reason_code if reason_code else None
        if expire_reserved_before is not None and row.expires_at <= expire_reserved_before:
            target_status = "expired"
            target_reason = "reservation_expired"
        if target_status == "expired":
            target_reason = "reservation_expired"

        estimated_units = max(0, int(row.estimated_units or 0))
        terminal_consumed_units = 0
        if target_status == "consumed":
            terminal_consumed_units = (
                max(0, int(consumed_units))
                if consumed_units is not None
                else estimated_units
            )

        cas_filters = [
            QuotaReservation.reservation_id == normalized_id,
            QuotaReservation.status == "reserved",
        ]
        if expire_reserved_before is not None:
            if target_status == "expired":
                cas_filters.append(QuotaReservation.expires_at <= expire_reserved_before)
            else:
                cas_filters.append(QuotaReservation.expires_at > expire_reserved_before)

        result = session.execute(
            update(QuotaReservation)
            .where(*cas_filters)
            .values(
                status=target_status,
                reason_code=target_reason,
                updated_at=current_time,
            )
            .execution_options(synchronize_session=False)
        )
        rowcount = result.rowcount
        if rowcount is None or rowcount < 0:
            raise RuntimeError("quota reservation CAS transition rowcount unavailable")
        if rowcount != 1:
            session.expire(row)
            fresh = session.execute(
                select(QuotaReservation)
                .where(QuotaReservation.reservation_id == normalized_id)
                .limit(1)
            ).scalar_one_or_none()
            reservation = fresh.to_dict() if fresh is not None else None
            status = str((reservation or {}).get("status") or "missing").strip().lower()
            return {
                "transitioned": False,
                "status": status,
                "reservation_id": normalized_id,
                "reservation": reservation,
            }

        self._move_quota_reserved_units_for_terminal_transition(
            session=session,
            row=row,
            consumed_units=terminal_consumed_units,
            now=current_time,
        )
        payload = row.to_dict()
        payload["status"] = target_status
        payload["reason_code"] = target_reason
        payload["updated_at"] = current_time.isoformat()
        return {
            "transitioned": True,
            "status": target_status,
            "reservation_id": normalized_id,
            "reservation": payload,
        }

    def _backfill_quota_usage_window_identity_keys(self, conn) -> None:
        rows = conn.exec_driver_sql(
            """
            SELECT id, owner_user_id, route_family, provider, model_tier
            FROM quota_usage_windows
            """
        ).mappings().all()
        for row in rows:
            identity = self.quota_window_identity_values(
                owner_user_id=row["owner_user_id"],
                route_family=row["route_family"],
                provider=row["provider"],
                model_tier=row["model_tier"],
            )
            conn.exec_driver_sql(
                """
                UPDATE quota_usage_windows
                SET window_identity_key = :window_identity_key
                WHERE id = :row_id
                """,
                {
                    "window_identity_key": identity["window_identity_key"],
                    "row_id": row["id"],
                },
            )

        duplicate = conn.exec_driver_sql(
            """
            SELECT window_identity_key, window_type, window_start, COUNT(*) AS row_count
            FROM quota_usage_windows
            GROUP BY window_identity_key, window_type, window_start
            HAVING COUNT(*) > 1
            LIMIT 1
            """
        ).fetchone()
        if duplicate is not None:
            raise RuntimeError(
                "duplicate quota usage window identity rows found; "
                "manual non-destructive merge is required before adding the unique index"
            )

    @staticmethod
    def _table_columns(conn, table_name: str) -> set[str]:
        rows = conn.exec_driver_sql(f"PRAGMA table_info({table_name})").fetchall()
        return {str(row[1]) for row in rows}

    def _add_column_if_missing(self, conn, table_name: str, column_name: str, column_sql: str) -> None:
        if column_name in self._table_columns(conn, table_name):
            return
        conn.exec_driver_sql(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}"
        )

    @staticmethod
    def _create_index_if_missing(conn, index_name: str, table_name: str, columns_sql: str) -> None:
        conn.exec_driver_sql(
            f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns_sql})"
        )

    @staticmethod
    def _create_unique_index_if_missing(conn, index_name: str, table_name: str, columns_sql: str) -> None:
        conn.exec_driver_sql(
            f"CREATE UNIQUE INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns_sql})"
        )

    @staticmethod
    def _ensure_bootstrap_admin_user_row(conn) -> None:
        now = datetime.now()
        conn.exec_driver_sql(
            """
            INSERT OR IGNORE INTO app_users (
                id,
                username,
                display_name,
                password_hash,
                mfa_enabled,
                role,
                is_active,
                created_at,
                updated_at
            ) VALUES (
                :id,
                :username,
                :display_name,
                NULL,
                0,
                :role,
                1,
                :created_at,
                :updated_at
            )
            """,
            {
                "id": BOOTSTRAP_ADMIN_USER_ID,
                "username": BOOTSTRAP_ADMIN_USERNAME,
                "display_name": BOOTSTRAP_ADMIN_DISPLAY_NAME,
                "role": ROLE_ADMIN,
                "created_at": now,
                "updated_at": now,
            },
        )

    @staticmethod
    def _seed_admin_rbac_compatibility_rows(conn) -> None:
        now = datetime.now()
        role_rows = [
            {
                "role_key": role_key,
                "display_name": role_key.replace("-", " ").title(),
                "description": "Built-in admin RBAC compatibility role",
                "created_at": now,
                "updated_at": now,
            }
            for role_key in ADMIN_RBAC_ROLES
        ]
        conn.exec_driver_sql(
            """
            INSERT OR IGNORE INTO admin_roles (
                role_key,
                display_name,
                description,
                built_in,
                created_at,
                updated_at
            ) VALUES (
                :role_key,
                :display_name,
                :description,
                1,
                :created_at,
                :updated_at
            )
            """,
            role_rows,
        )

        capability_rows = []
        for role_key, capabilities in ADMIN_RBAC_ROLE_CAPABILITIES.items():
            for capability in capabilities:
                capability_rows.append(
                    {
                        "role_key": role_key,
                        "capability": capability,
                        "created_at": now,
                    }
                )
        conn.exec_driver_sql(
            """
            INSERT OR IGNORE INTO admin_role_capabilities (
                role_key,
                capability,
                created_at
            ) VALUES (
                :role_key,
                :capability,
                :created_at
            )
            """,
            capability_rows,
        )

    def _migrate_backtest_summaries_table(self, conn, *, bootstrap_user_id: str) -> None:
        columns = self._table_columns(conn, "backtest_summaries")
        if "owner_id" in columns:
            conn.exec_driver_sql(
                "UPDATE backtest_summaries SET owner_id = :owner_id "
                "WHERE owner_id IS NULL OR TRIM(owner_id) = ''",
                {"owner_id": bootstrap_user_id},
            )
            return

        conn.exec_driver_sql(
            """
            CREATE TABLE backtest_summaries__new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id VARCHAR(64) NOT NULL,
                scope VARCHAR(16) NOT NULL,
                code VARCHAR(16),
                eval_window_days INTEGER NOT NULL DEFAULT 10,
                engine_version VARCHAR(16) NOT NULL DEFAULT 'v1',
                computed_at DATETIME,
                total_evaluations INTEGER DEFAULT 0,
                completed_count INTEGER DEFAULT 0,
                insufficient_count INTEGER DEFAULT 0,
                long_count INTEGER DEFAULT 0,
                cash_count INTEGER DEFAULT 0,
                win_count INTEGER DEFAULT 0,
                loss_count INTEGER DEFAULT 0,
                neutral_count INTEGER DEFAULT 0,
                direction_accuracy_pct FLOAT,
                win_rate_pct FLOAT,
                neutral_rate_pct FLOAT,
                avg_stock_return_pct FLOAT,
                avg_simulated_return_pct FLOAT,
                stop_loss_trigger_rate FLOAT,
                take_profit_trigger_rate FLOAT,
                ambiguous_rate FLOAT,
                avg_days_to_first_hit FLOAT,
                advice_breakdown_json TEXT,
                diagnostics_json TEXT,
                CONSTRAINT uix_backtest_summary_owner_scope_code_window_version
                    UNIQUE (owner_id, scope, code, eval_window_days, engine_version)
            )
            """
        )
        conn.exec_driver_sql(
            """
            INSERT INTO backtest_summaries__new (
                id,
                owner_id,
                scope,
                code,
                eval_window_days,
                engine_version,
                computed_at,
                total_evaluations,
                completed_count,
                insufficient_count,
                long_count,
                cash_count,
                win_count,
                loss_count,
                neutral_count,
                direction_accuracy_pct,
                win_rate_pct,
                neutral_rate_pct,
                avg_stock_return_pct,
                avg_simulated_return_pct,
                stop_loss_trigger_rate,
                take_profit_trigger_rate,
                ambiguous_rate,
                avg_days_to_first_hit,
                advice_breakdown_json,
                diagnostics_json
            )
            SELECT
                id,
                :owner_id,
                scope,
                code,
                eval_window_days,
                engine_version,
                computed_at,
                total_evaluations,
                completed_count,
                insufficient_count,
                long_count,
                cash_count,
                win_count,
                loss_count,
                neutral_count,
                direction_accuracy_pct,
                win_rate_pct,
                neutral_rate_pct,
                avg_stock_return_pct,
                avg_simulated_return_pct,
                stop_loss_trigger_rate,
                take_profit_trigger_rate,
                ambiguous_rate,
                avg_days_to_first_hit,
                advice_breakdown_json,
                diagnostics_json
            FROM backtest_summaries
            """,
            {"owner_id": bootstrap_user_id},
        )
        conn.exec_driver_sql("DROP TABLE backtest_summaries")
        conn.exec_driver_sql("ALTER TABLE backtest_summaries__new RENAME TO backtest_summaries")

    def _backfill_market_scanner_ownership(self, conn, *, bootstrap_user_id: str) -> None:
        rows = conn.exec_driver_sql(
            """
            SELECT id, owner_id, scope, summary_json, diagnostics_json
            FROM market_scanner_runs
            ORDER BY id ASC
            """
        ).fetchall()
        for row in rows:
            row_id = int(row[0])
            owner_id = str(row[1] or "").strip() or None
            current_scope = str(row[2] or "").strip().lower()
            summary = self._safe_json_loads(row[3], {})
            diagnostics = self._safe_json_loads(row[4], {})
            operation = diagnostics.get("operation") if isinstance(diagnostics, dict) else {}
            trigger_mode = ""
            request_source = ""
            if isinstance(operation, dict):
                trigger_mode = str(operation.get("trigger_mode") or "").strip().lower()
                request_source = str(operation.get("request_source") or "").strip().lower()
            if not trigger_mode and isinstance(summary, dict):
                trigger_mode = str(summary.get("trigger_mode") or "").strip().lower()
                request_source = request_source or str(summary.get("request_source") or "").strip().lower()

            inferred_scope = OWNERSHIP_SCOPE_SYSTEM if (
                trigger_mode == "scheduled" or request_source in {"scheduler", "system"}
            ) else OWNERSHIP_SCOPE_USER
            if inferred_scope == OWNERSHIP_SCOPE_SYSTEM:
                next_scope = OWNERSHIP_SCOPE_SYSTEM
            elif current_scope in {OWNERSHIP_SCOPE_USER, OWNERSHIP_SCOPE_SYSTEM}:
                next_scope = current_scope
            else:
                next_scope = inferred_scope
            next_owner_id = None if next_scope == OWNERSHIP_SCOPE_SYSTEM else (owner_id or bootstrap_user_id)
            conn.exec_driver_sql(
                "UPDATE market_scanner_runs SET owner_id = :owner_id, scope = :scope WHERE id = :id",
                {"id": row_id, "owner_id": next_owner_id, "scope": next_scope},
            )

    def _backfill_conversation_sessions(self, conn, *, bootstrap_user_id: str) -> None:
        rows = conn.exec_driver_sql(
            """
            SELECT
                session_id,
                MIN(created_at) AS created_at,
                MAX(created_at) AS updated_at
            FROM conversation_messages
            GROUP BY session_id
            """
        ).fetchall()
        for row in rows:
            session_id = str(row[0] or "").strip()
            if not session_id:
                continue
            title_row = conn.exec_driver_sql(
                """
                SELECT content
                FROM conversation_messages
                WHERE session_id = :session_id AND role = 'user'
                ORDER BY created_at ASC, id ASC
                LIMIT 1
                """,
                {"session_id": session_id},
            ).fetchone()
            title = str(title_row[0])[:255] if title_row and title_row[0] else None
            conn.exec_driver_sql(
                """
                INSERT OR IGNORE INTO conversation_sessions (
                    session_id,
                    owner_id,
                    title,
                    created_at,
                    updated_at
                ) VALUES (
                    :session_id,
                    :owner_id,
                    :title,
                    :created_at,
                    :updated_at
                )
                """,
                {
                    "session_id": session_id,
                    "owner_id": bootstrap_user_id,
                    "title": title,
                    "created_at": row[1],
                    "updated_at": row[2],
                },
            )
        conn.exec_driver_sql(
            "UPDATE conversation_sessions SET owner_id = :owner_id "
            "WHERE owner_id IS NULL OR TRIM(owner_id) = ''",
            {"owner_id": bootstrap_user_id},
        )

    @staticmethod
    def _safe_json_loads(value: Any, fallback: Any) -> Any:
        if not value:
            return fallback
        try:
            return json.loads(value)
        except Exception:
            return fallback

    def _sqlite_get_app_user(self, user_id: str) -> Optional[AppUser]:
        normalized = str(user_id or "").strip()
        if not normalized:
            return None
        with self.get_session() as session:
            return session.execute(
                select(AppUser).where(AppUser.id == normalized).limit(1)
            ).scalar_one_or_none()

    def _sqlite_get_app_user_by_username(self, username: str) -> Optional[AppUser]:
        normalized = str(username or "").strip()
        if not normalized:
            return None
        with self.get_session() as session:
            return session.execute(
                select(AppUser).where(AppUser.username == normalized).limit(1)
            ).scalar_one_or_none()

    def _sqlite_list_app_users(self) -> List[AppUser]:
        with self.get_session() as session:
            return list(
                session.execute(
                    select(AppUser).order_by(desc(AppUser.created_at), desc(AppUser.id))
                ).scalars().all()
            )

    def _sqlite_create_or_update_app_user(
        self,
        *,
        user_id: str,
        username: str,
        role: str = ROLE_USER,
        display_name: Optional[str] = None,
        password_hash: Optional[str] = None,
        mfa_enabled: Optional[bool] = None,
        mfa_secret_ref: Optional[str] = None,
        mfa_recovery_codes_hash: Optional[str] = None,
        mfa_created_at: Optional[datetime] = None,
        mfa_enabled_at: Optional[datetime] = None,
        mfa_last_verified_at: Optional[datetime] = None,
        is_active: bool = True,
    ) -> AppUser:
        normalized_id = str(user_id or "").strip()
        normalized_username = str(username or "").strip()
        if not normalized_id:
            raise ValueError("user_id is required")
        if not normalized_username:
            raise ValueError("username is required")
        normalized_role = normalize_role(role)

        with self.get_session() as session:
            row = session.execute(
                select(AppUser).where(AppUser.id == normalized_id).limit(1)
            ).scalar_one_or_none()
            if row is None:
                row = AppUser(
                    id=normalized_id,
                    username=normalized_username,
                    display_name=(display_name or "").strip() or None,
                    password_hash=password_hash,
                    mfa_enabled=bool(mfa_enabled) if mfa_enabled is not None else False,
                    mfa_secret_ref=mfa_secret_ref,
                    mfa_recovery_codes_hash=mfa_recovery_codes_hash,
                    mfa_created_at=mfa_created_at,
                    mfa_enabled_at=mfa_enabled_at,
                    mfa_last_verified_at=mfa_last_verified_at,
                    role=normalized_role,
                    is_active=bool(is_active),
                )
                session.add(row)
            else:
                row.username = normalized_username
                row.display_name = (display_name or "").strip() or row.display_name
                row.password_hash = password_hash if password_hash is not None else row.password_hash
                if mfa_enabled is not None:
                    row.mfa_enabled = bool(mfa_enabled)
                if mfa_secret_ref is not None:
                    row.mfa_secret_ref = mfa_secret_ref
                if mfa_recovery_codes_hash is not None:
                    row.mfa_recovery_codes_hash = mfa_recovery_codes_hash
                if mfa_created_at is not None:
                    row.mfa_created_at = mfa_created_at
                if mfa_enabled_at is not None:
                    row.mfa_enabled_at = mfa_enabled_at
                if mfa_last_verified_at is not None:
                    row.mfa_last_verified_at = mfa_last_verified_at
                row.role = normalized_role
                row.is_active = bool(is_active)
                row.updated_at = datetime.now()
            session.commit()
            session.refresh(row)
            return row

    def _sqlite_update_app_user_mfa(
        self,
        *,
        user_id: str,
        mfa_enabled: bool,
        mfa_secret_ref: Optional[str] = None,
        mfa_recovery_codes_hash: Optional[str] = None,
        mfa_created_at: Optional[datetime] = None,
        mfa_enabled_at: Optional[datetime] = None,
        mfa_last_verified_at: Optional[datetime] = None,
    ) -> Optional[AppUser]:
        normalized_id = str(user_id or "").strip()
        if not normalized_id:
            return None
        with self.get_session() as session:
            row = session.execute(
                select(AppUser).where(AppUser.id == normalized_id).limit(1)
            ).scalar_one_or_none()
            if row is None:
                return None
            row.mfa_enabled = bool(mfa_enabled)
            row.mfa_secret_ref = mfa_secret_ref
            row.mfa_recovery_codes_hash = mfa_recovery_codes_hash
            if mfa_created_at is not None:
                row.mfa_created_at = mfa_created_at
            if mfa_enabled_at is not None:
                row.mfa_enabled_at = mfa_enabled_at
            if mfa_last_verified_at is not None:
                row.mfa_last_verified_at = mfa_last_verified_at
            row.updated_at = datetime.now()
            session.commit()
            session.refresh(row)
            return row

    def _sqlite_get_app_user_session(self, session_id: str) -> Optional[AppUserSession]:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return None
        with self.get_session() as session:
            return self._sqlite_find_app_user_session_row(session, session_id=normalized_session_id)

    def _sqlite_list_app_user_sessions(self, user_id: Optional[str] = None) -> List[AppUserSession]:
        normalized_user_id = str(user_id or "").strip()
        with self.get_session() as session:
            query = select(AppUserSession)
            if normalized_user_id:
                query = query.where(AppUserSession.user_id == normalized_user_id)
            return list(
                session.execute(
                    query.order_by(desc(AppUserSession.created_at), desc(AppUserSession.session_id))
                ).scalars().all()
            )

    def _sqlite_find_app_user_session_row(
        self,
        session: Session,
        *,
        session_id: str,
    ) -> Optional[AppUserSession]:
        return session.execute(
            select(AppUserSession).where(AppUserSession.session_id == session_id).limit(1)
        ).scalar_one_or_none()

    def _sqlite_create_or_update_app_user_session(
        self,
        *,
        session_id: str,
        user_id: str,
        expires_at: datetime,
        created_at: Optional[datetime] = None,
        last_seen_at: Optional[datetime] = None,
        revoked_at: Optional[datetime] = None,
    ) -> AppUserSession:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            raise ValueError("session_id is required")
        resolved_user_id = self.require_user_id(user_id)
        if not isinstance(expires_at, datetime):
            raise ValueError("expires_at must be a datetime")

        with self.get_session() as session:
            row = session.execute(
                select(AppUserSession).where(AppUserSession.session_id == normalized_session_id).limit(1)
            ).scalar_one_or_none()
            now = datetime.now()
            if row is None:
                row = AppUserSession(
                    session_id=normalized_session_id,
                    user_id=resolved_user_id,
                    created_at=created_at or now,
                    last_seen_at=last_seen_at or now,
                    expires_at=expires_at,
                    revoked_at=revoked_at,
                )
                session.add(row)
            else:
                row.user_id = resolved_user_id
                row.last_seen_at = last_seen_at or now
                row.expires_at = expires_at
                row.revoked_at = revoked_at
            session.commit()
            session.refresh(row)
            return row

    def _sqlite_touch_app_user_session(self, session_id: str) -> bool:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return False
        with self.get_session() as session:
            row = self._sqlite_find_app_user_session_row(session, session_id=normalized_session_id)
            if row is None:
                return False
            row.last_seen_at = datetime.now()
            session.commit()
            return True

    def _sqlite_revoke_app_user_session(self, session_id: str) -> bool:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return False
        with self.get_session() as session:
            row = self._sqlite_find_app_user_session_row(session, session_id=normalized_session_id)
            if row is None:
                return False
            row.revoked_at = datetime.now()
            row.last_seen_at = datetime.now()
            session.commit()
            return True

    def _sqlite_revoke_all_app_user_sessions(self, user_id: str) -> int:
        resolved_user_id = self.require_user_id(user_id)
        with self.get_session() as session:
            rows = session.execute(
                select(AppUserSession).where(
                    and_(
                        AppUserSession.user_id == resolved_user_id,
                        AppUserSession.revoked_at.is_(None),
                    )
                )
            ).scalars().all()
            if not rows:
                return 0
            now = datetime.now()
            for row in rows:
                row.revoked_at = now
                row.last_seen_at = now
            session.commit()
            return len(rows)

    def _sqlite_list_active_app_user_session_ids(self, user_id: str) -> List[str]:
        resolved_user_id = self.require_user_id(user_id)
        with self.get_session() as session:
            rows = session.execute(
                select(AppUserSession.session_id).where(
                    and_(
                        AppUserSession.user_id == resolved_user_id,
                        AppUserSession.revoked_at.is_(None),
                    )
                )
            ).scalars().all()
            return [str(value) for value in rows if str(value or "").strip()]

    def _sqlite_get_user_preference_row(self, user_id: str) -> Optional[UserPreference]:
        normalized_user_id = str(user_id or "").strip()
        if not normalized_user_id:
            return None
        with self.get_session() as session:
            return session.execute(
                select(UserPreference).where(UserPreference.user_id == normalized_user_id).limit(1)
            ).scalar_one_or_none()

    def _collect_known_user_ids(self) -> List[str]:
        with self.get_session() as session:
            sqlite_user_ids = {
                str(value)
                for value in session.execute(
                    select(AppUser.id).where(AppUser.id != BOOTSTRAP_ADMIN_USER_ID)
                ).scalars().all()
                if str(value or "").strip()
            }
        if self._phase_a_enabled and self._phase_a_store is not None:
            sqlite_user_ids.update(self._phase_a_store.list_non_bootstrap_user_ids())
        return sorted(sqlite_user_ids)

    def _sync_phase_a_user_from_legacy(self, row: AppUser) -> Any:
        if not self._phase_a_enabled or self._phase_a_store is None or row is None:
            return row
        return self._phase_a_store.upsert_app_user(
            user_id=str(row.id),
            username=str(row.username),
            role=str(row.role),
            display_name=getattr(row, "display_name", None),
            password_hash=getattr(row, "password_hash", None),
            mfa_enabled=bool(getattr(row, "mfa_enabled", False)),
            mfa_secret_ref=getattr(row, "mfa_secret_ref", None),
            mfa_recovery_codes_hash=getattr(row, "mfa_recovery_codes_hash", None),
            mfa_created_at=getattr(row, "mfa_created_at", None),
            mfa_enabled_at=getattr(row, "mfa_enabled_at", None),
            mfa_last_verified_at=getattr(row, "mfa_last_verified_at", None),
            is_active=bool(getattr(row, "is_active", True)),
            created_at=getattr(row, "created_at", None),
            updated_at=getattr(row, "updated_at", None),
        )

    def _sync_phase_a_session_from_legacy(self, row: AppUserSession) -> Any:
        if not self._phase_a_enabled or self._phase_a_store is None or row is None:
            return row
        user_row = self.get_app_user(str(row.user_id))
        if user_row is None:
            return None
        return self._phase_a_store.upsert_app_user_session(
            session_id=str(row.session_id),
            user_id=str(row.user_id),
            expires_at=row.expires_at,
            created_at=getattr(row, "created_at", None),
            last_seen_at=getattr(row, "last_seen_at", None),
            revoked_at=getattr(row, "revoked_at", None),
        )

    def _sync_phase_a_notification_preferences_from_legacy(self, user_id: str) -> Optional[Dict[str, Any]]:
        if not self._phase_a_enabled or self._phase_a_store is None:
            return None
        row = self._sqlite_get_user_preference_row(user_id)
        if row is None:
            return None
        payload = self._safe_json_loads(
            getattr(row, "notification_preferences_json", None),
            {},
        )
        if not isinstance(payload, dict):
            return None
        self.get_app_user(user_id)
        return self._phase_a_store.import_legacy_notification_preferences(
            user_id,
            payload,
            updated_at=getattr(row, "updated_at", None),
        )

    def ensure_bootstrap_admin_user(self) -> AppUser:
        existing = self.get_app_user(BOOTSTRAP_ADMIN_USER_ID)
        if existing is not None:
            return existing
        return self.create_or_update_app_user(
            user_id=BOOTSTRAP_ADMIN_USER_ID,
            username=BOOTSTRAP_ADMIN_USERNAME,
            role=ROLE_ADMIN,
            display_name=BOOTSTRAP_ADMIN_DISPLAY_NAME,
            password_hash=None,
            is_active=True,
        )

    def get_default_owner_id(self) -> str:
        user = self.ensure_bootstrap_admin_user()
        return str(user.id)

    def require_user_id(self, owner_id: Optional[str], *, allow_none: bool = False) -> Optional[str]:
        normalized = str(owner_id or "").strip()
        if not normalized:
            return None if allow_none else self.get_default_owner_id()
        if self.get_app_user(normalized) is None:
            raise ValueError(f"Unknown app user: {normalized}")
        return normalized

    @staticmethod
    def _hash_optional_key(value: Optional[str]) -> Optional[str]:
        text = str(value or "").strip()
        if not text:
            return None
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def _resolve_bounded_limit(value: Optional[int], *, default: int, high: int) -> int:
        try:
            resolved = int(value) if value is not None else int(default)
        except (TypeError, ValueError):
            resolved = int(default)
        if resolved <= 0:
            resolved = int(default)
        return min(resolved, int(high))

    @staticmethod
    def _sanitize_task_metadata(value: Any) -> Dict[str, Any]:
        """Sanitize durable task metadata and drop secret-like/internal payload keys."""
        blocked_key_fragments = (
            "auth",
            "cookie",
            "exception",
            "payload",
            "prompt",
            "raw",
            "request",
            "response",
            "session",
            "stack",
            "trace",
            "traceback",
            "url",
            "webhook",
        )

        def scrub(obj: Any) -> Any:
            if isinstance(obj, dict):
                cleaned: Dict[str, Any] = {}
                for key, item in obj.items():
                    key_text = str(key)
                    key_lower = key_text.lower()
                    if is_sensitive_key(key_text) or any(fragment in key_lower for fragment in blocked_key_fragments):
                        continue
                    scrubbed = scrub(item)
                    if scrubbed is not None:
                        cleaned[key_text[:80]] = scrubbed
                return cleaned
            if isinstance(obj, list):
                values = [scrub(item) for item in obj[:50]]
                return [item for item in values if item is not None]
            if isinstance(obj, tuple):
                values = [scrub(item) for item in obj[:50]]
                return [item for item in values if item is not None]
            if isinstance(obj, str):
                text = obj.strip()
                lowered = text.lower()
                if (
                    "http://" in lowered
                    or "https://" in lowered
                    or "traceback (most recent call last)" in lowered
                    or "api_key" in lowered
                    or "token=" in lowered
                    or "cookie=" in lowered
                    or "session=" in lowered
                    or "authorization:" in lowered
                    or "bearer " in lowered
                ):
                    return None
                return sanitize_message(text)[:500]
            return obj

        sanitized = sanitize_metadata(scrub(value or {}))
        return sanitized if isinstance(sanitized, dict) else {}

    @staticmethod
    def _sanitize_task_error_summary(value: Any) -> Optional[str]:
        text = sanitize_message(str(value or "").strip())
        if not text:
            return None
        if "Traceback (most recent call last)" in text or "\n" in text:
            return "Task failed; see server logs for sanitized details"
        return text[:240]

    @staticmethod
    def _durable_task_payload(row: DurableTaskState) -> Dict[str, Any]:
        return row.to_dict()

    @staticmethod
    def _sanitize_task_progress_message(value: Any) -> Optional[str]:
        text = sanitize_message(str(value or "").strip())
        if not text:
            return None
        if "Traceback (most recent call last)" in text or "\n" in text:
            return "Task progress update unavailable; see server logs for sanitized details"
        return text[:500]

    @staticmethod
    def _durable_task_progress_payload(row: DurableTaskProgressEvent) -> Dict[str, Any]:
        return row.to_dict()

    @staticmethod
    def _bounded_durable_task_progress_limit(limit: int) -> int:
        return max(1, min(int(limit or 50), 100))

    @staticmethod
    def _is_durable_task_active_status(status: Optional[str]) -> bool:
        return str(status or "").strip().lower() in DURABLE_TASK_ACTIVE_STATUSES

    @staticmethod
    def _active_dedupe_key_hash_for_row(dedupe_key_hash: Optional[str], status: Optional[str]) -> Optional[str]:
        if not dedupe_key_hash:
            return None
        return dedupe_key_hash if DatabaseManager._is_durable_task_active_status(status) else None

    def _find_active_durable_task_duplicate(
        self,
        *,
        session: Session,
        owner_user_id: str,
        task_type: str,
        active_dedupe_key_hash: Optional[str],
        exclude_task_id: Optional[str] = None,
    ) -> Optional[DurableTaskState]:
        if not active_dedupe_key_hash:
            return None
        query = select(DurableTaskState).where(
            DurableTaskState.owner_user_id == owner_user_id,
            DurableTaskState.task_type == task_type,
            DurableTaskState.status.in_(tuple(DURABLE_TASK_ACTIVE_STATUSES)),
            or_(
                DurableTaskState.active_dedupe_key_hash == active_dedupe_key_hash,
                and_(
                    DurableTaskState.active_dedupe_key_hash.is_(None),
                    DurableTaskState.dedupe_key_hash == active_dedupe_key_hash,
                ),
            ),
        )
        normalized_exclude = str(exclude_task_id or "").strip()
        if normalized_exclude:
            query = query.where(DurableTaskState.task_id != normalized_exclude)
        return session.execute(
            query.order_by(asc(DurableTaskState.created_at), asc(DurableTaskState.id)).limit(1)
        ).scalar_one_or_none()

    def _store_durable_task_state(
        self,
        *,
        task_id: str,
        owner_user_id: Optional[str],
        task_type: str,
        status: str = "pending",
        progress: int = 0,
        current_step: Optional[str] = None,
        route_family: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        dedupe_key: Optional[str] = None,
        max_attempts: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        normalized_task_id = str(task_id or "").strip()
        if not normalized_task_id:
            raise ValueError("task_id is required")
        resolved_owner_id = self.require_user_id(owner_user_id)
        now = datetime.now()
        safe_metadata = self._sanitize_task_metadata(metadata or {})
        status_text = str(status or "pending")[:32]
        dedupe_key_hash = self._hash_optional_key(dedupe_key)
        active_dedupe_key_hash = self._active_dedupe_key_hash_for_row(dedupe_key_hash, status_text)

        def write(active_session: Session) -> Dict[str, Any]:
            row = active_session.execute(
                select(DurableTaskState)
                .where(DurableTaskState.task_id == normalized_task_id)
                .limit(1)
            ).scalar_one_or_none()
            if row is None:
                row = DurableTaskState(
                    task_id=normalized_task_id,
                    owner_user_id=resolved_owner_id,
                    task_type=str(task_type or "analysis")[:32],
                    created_at=now,
                )
                active_session.add(row)
            row.owner_user_id = resolved_owner_id
            row.task_type = str(task_type or "analysis")[:32]
            row.route_family = str(route_family or "")[:64] or None
            row.status = status_text
            row.progress = max(0, min(int(progress or 0), 100))
            row.current_step = sanitize_message(str(current_step or ""))[:500] or None
            if max_attempts is not None:
                row.max_attempts = max(1, min(int(max_attempts or 1), 10))
            elif not row.max_attempts:
                row.max_attempts = 1
            row.attempt_count = max(0, int(row.attempt_count or 0))
            row.idempotency_key_hash = self._hash_optional_key(idempotency_key)
            row.dedupe_key_hash = dedupe_key_hash
            row.active_dedupe_key_hash = active_dedupe_key_hash
            row.metadata_json = self._safe_json_dumps(safe_metadata)
            row.updated_at = now
            if row.status in {"processing", "running"} and row.started_at is None:
                row.started_at = now
            active_session.flush()
            return self._durable_task_payload(row)

        if session is not None:
            return write(session)
        with self.session_scope() as scoped_session:
            return write(scoped_session)

    def reserve_durable_task_state(
        self,
        *,
        task_id: str,
        owner_user_id: Optional[str],
        task_type: str,
        status: str = "pending",
        progress: int = 0,
        current_step: Optional[str] = None,
        route_family: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        dedupe_key: Optional[str] = None,
        max_attempts: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        normalized_task_id = str(task_id or "").strip()
        if not normalized_task_id:
            raise ValueError("task_id is required")
        resolved_owner_id = self.require_user_id(owner_user_id)
        normalized_task_type = str(task_type or "analysis")[:32]
        status_text = str(status or "pending")[:32]
        dedupe_key_hash = self._hash_optional_key(dedupe_key)
        active_dedupe_key_hash = self._active_dedupe_key_hash_for_row(dedupe_key_hash, status_text)

        try:
            with self.session_scope() as session:
                duplicate_row = self._find_active_durable_task_duplicate(
                    session=session,
                    owner_user_id=resolved_owner_id,
                    task_type=normalized_task_type,
                    active_dedupe_key_hash=active_dedupe_key_hash,
                    exclude_task_id=normalized_task_id,
                )
                if duplicate_row is not None:
                    return None, self._durable_task_payload(duplicate_row)

                payload = self._store_durable_task_state(
                    task_id=normalized_task_id,
                    owner_user_id=resolved_owner_id,
                    task_type=normalized_task_type,
                    status=status_text,
                    progress=progress,
                    current_step=current_step,
                    route_family=route_family,
                    idempotency_key=idempotency_key,
                    dedupe_key=dedupe_key,
                    max_attempts=max_attempts,
                    metadata=metadata,
                    session=session,
                )
                return payload, None
        except IntegrityError:
            with self.get_session() as session:
                duplicate_row = self._find_active_durable_task_duplicate(
                    session=session,
                    owner_user_id=resolved_owner_id,
                    task_type=normalized_task_type,
                    active_dedupe_key_hash=active_dedupe_key_hash,
                    exclude_task_id=normalized_task_id,
                )
                if duplicate_row is not None:
                    return None, self._durable_task_payload(duplicate_row)
            raise

    def create_durable_task_state(
        self,
        *,
        task_id: str,
        owner_user_id: Optional[str],
        task_type: str,
        status: str = "pending",
        progress: int = 0,
        current_step: Optional[str] = None,
        route_family: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        dedupe_key: Optional[str] = None,
        max_attempts: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload, duplicate = self.reserve_durable_task_state(
            task_id=task_id,
            owner_user_id=owner_user_id,
            task_type=task_type,
            status=status,
            progress=progress,
            current_step=current_step,
            route_family=route_family,
            idempotency_key=idempotency_key,
            dedupe_key=dedupe_key,
            max_attempts=max_attempts,
            metadata=metadata,
        )
        if duplicate is not None:
            raise IntegrityError("active durable task duplicate", params=None, orig=None)
        if payload is None:
            raise RuntimeError("failed to create durable task state")
        return payload

    def append_durable_task_progress_event(
        self,
        *,
        task_id: str,
        owner_user_id: Optional[str],
        event_type: str,
        stage: Optional[str] = None,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        normalized_task_id = str(task_id or "").strip()
        if not normalized_task_id:
            raise ValueError("task_id is required")
        resolved_owner_id = self.require_user_id(owner_user_id)
        safe_event_type = sanitize_message(str(event_type or "progress").strip())[:32] or "progress"
        safe_progress = None if progress is None else max(0, min(int(progress or 0), 100))
        safe_metadata = self._sanitize_task_metadata(metadata or {})
        current_time = created_at or datetime.now()
        with self.session_scope() as session:
            task_row = session.execute(
                select(DurableTaskState)
                .where(
                    DurableTaskState.task_id == normalized_task_id,
                    DurableTaskState.owner_user_id == resolved_owner_id,
                )
                .limit(1)
            ).scalar_one_or_none()
            if task_row is None:
                raise ValueError("durable task not found")
            next_sequence = session.execute(
                select(func.max(DurableTaskProgressEvent.sequence))
                .where(DurableTaskProgressEvent.task_id == normalized_task_id)
            ).scalar_one_or_none()
            row = DurableTaskProgressEvent(
                task_id=normalized_task_id,
                owner_user_id=resolved_owner_id,
                sequence=int(next_sequence or 0) + 1,
                event_type=safe_event_type,
                stage=sanitize_message(str(stage or "").strip())[:64] or None,
                progress=safe_progress,
                message_safe=self._sanitize_task_progress_message(message),
                metadata_json=self._safe_json_dumps(safe_metadata),
                created_at=current_time,
            )
            session.add(row)
            session.flush()
            return self._durable_task_progress_payload(row)

    def list_durable_task_progress_events(
        self,
        *,
        task_id: str,
        owner_user_id: Optional[str],
        after_sequence: Optional[int] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        normalized_task_id = str(task_id or "").strip()
        if not normalized_task_id:
            return []
        resolved_owner_id = self.require_user_id(owner_user_id)
        safe_limit = self._bounded_durable_task_progress_limit(limit)
        with self.get_session() as session:
            task_row = session.execute(
                select(DurableTaskState.id)
                .where(
                    DurableTaskState.task_id == normalized_task_id,
                    DurableTaskState.owner_user_id == resolved_owner_id,
                )
                .limit(1)
            ).scalar_one_or_none()
            if task_row is None:
                return []
            query = select(DurableTaskProgressEvent).where(
                DurableTaskProgressEvent.task_id == normalized_task_id,
                DurableTaskProgressEvent.owner_user_id == resolved_owner_id,
            )
            if after_sequence is not None:
                query = query.where(DurableTaskProgressEvent.sequence > max(0, int(after_sequence or 0)))
            rows = session.execute(
                query.order_by(asc(DurableTaskProgressEvent.sequence)).limit(safe_limit)
            ).scalars().all()
            return [self._durable_task_progress_payload(row) for row in rows]

    def list_durable_task_progress_events_after(
        self,
        *,
        task_id: str,
        owner_user_id: Optional[str],
        after_sequence: int,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        return self.list_durable_task_progress_events(
            task_id=task_id,
            owner_user_id=owner_user_id,
            after_sequence=after_sequence,
            limit=limit,
        )

    def get_latest_durable_task_progress_summary(
        self,
        *,
        task_id: str,
        owner_user_id: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        normalized_task_id = str(task_id or "").strip()
        if not normalized_task_id:
            return None
        resolved_owner_id = self.require_user_id(owner_user_id)
        with self.get_session() as session:
            row = session.execute(
                select(DurableTaskProgressEvent)
                .where(
                    DurableTaskProgressEvent.task_id == normalized_task_id,
                    DurableTaskProgressEvent.owner_user_id == resolved_owner_id,
                )
                .order_by(desc(DurableTaskProgressEvent.sequence))
                .limit(1)
            ).scalar_one_or_none()
            return self._durable_task_progress_payload(row) if row is not None else None

    def update_durable_task_state(
        self,
        *,
        task_id: str,
        owner_user_id: Optional[str] = None,
        status: Optional[str] = None,
        progress: Optional[int] = None,
        current_step: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        failed_at: Optional[datetime] = None,
        cancelled_at: Optional[datetime] = None,
        error_code: Optional[str] = None,
        error_summary: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        normalized_task_id = str(task_id or "").strip()
        if not normalized_task_id:
            return None
        resolved_owner_id = self.require_user_id(owner_user_id) if owner_user_id else None
        now = datetime.now()
        with self.session_scope() as session:
            query = select(DurableTaskState).where(DurableTaskState.task_id == normalized_task_id)
            if resolved_owner_id:
                query = query.where(DurableTaskState.owner_user_id == resolved_owner_id)
            row = session.execute(query.limit(1)).scalar_one_or_none()
            if row is None:
                return None
            if status is not None:
                row.status = str(status or "")[:32]
                row.active_dedupe_key_hash = self._active_dedupe_key_hash_for_row(
                    row.dedupe_key_hash,
                    row.status,
                )
            if progress is not None:
                row.progress = max(0, min(int(progress or 0), 100))
            if current_step is not None:
                row.current_step = sanitize_message(str(current_step or ""))[:500] or None
            if metadata is not None:
                prior = self._safe_json_loads(row.metadata_json, {})
                if not isinstance(prior, dict):
                    prior = {}
                prior.update(self._sanitize_task_metadata(metadata))
                row.metadata_json = self._safe_json_dumps(prior)
            if started_at is not None:
                row.started_at = started_at
            if completed_at is not None:
                row.completed_at = completed_at
            if failed_at is not None:
                row.failed_at = failed_at
            if cancelled_at is not None:
                row.cancelled_at = cancelled_at
            if error_code is not None:
                row.error_code = str(error_code or "")[:64] or None
            if error_summary is not None:
                row.error_summary = self._sanitize_task_error_summary(error_summary)
            row.updated_at = now
            session.flush()
            return self._durable_task_payload(row)

    def claim_next_durable_task_state(
        self,
        *,
        worker_id: str,
        task_type: str,
        lease_seconds: int = 60,
        now: Optional[datetime] = None,
    ) -> Optional[Dict[str, Any]]:
        normalized_worker = sanitize_message(str(worker_id or "").strip())[:128]
        normalized_task_type = str(task_type or "").strip()[:32]
        if not normalized_worker or not normalized_task_type:
            return None
        lease_seconds = max(1, min(int(lease_seconds or 60), 3600))
        current_time = now or datetime.now()
        claimable_statuses = ("queued", "pending", "waiting_retry")
        recoverable_statuses = ("leased", "processing")
        with self.session_scope() as session:
            row = session.execute(
                select(DurableTaskState)
                .where(
                    DurableTaskState.task_type == normalized_task_type,
                    or_(
                        and_(
                            DurableTaskState.status.in_(claimable_statuses),
                            or_(
                                DurableTaskState.lease_expires_at.is_(None),
                                DurableTaskState.lease_expires_at <= current_time,
                            ),
                        ),
                        and_(
                            DurableTaskState.status.in_(recoverable_statuses),
                            DurableTaskState.lease_expires_at <= current_time,
                        ),
                    ),
                )
                .order_by(asc(DurableTaskState.created_at), asc(DurableTaskState.id))
                .limit(1)
            ).scalar_one_or_none()
            if row is None:
                return None
            row.status = "leased"
            row.lease_owner = normalized_worker
            row.lease_expires_at = current_time + timedelta(seconds=lease_seconds)
            row.active_dedupe_key_hash = self._active_dedupe_key_hash_for_row(
                row.dedupe_key_hash,
                row.status,
            )
            row.attempt_count = max(0, int(row.attempt_count or 0)) + 1
            row.max_attempts = max(1, int(row.max_attempts or 1))
            row.updated_at = current_time
            if row.started_at is None:
                row.started_at = current_time
            session.flush()
            return self._durable_task_payload(row)

    def heartbeat_durable_task_state(
        self,
        *,
        task_id: str,
        worker_id: str,
        lease_seconds: int = 60,
        status: str = "processing",
        progress: Optional[int] = None,
        current_step: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        now: Optional[datetime] = None,
    ) -> Optional[Dict[str, Any]]:
        normalized_worker = sanitize_message(str(worker_id or "").strip())[:128]
        if not normalized_worker:
            return None
        current_time = now or datetime.now()
        with self.session_scope() as session:
            row = session.execute(
                select(DurableTaskState)
                .where(
                    DurableTaskState.task_id == str(task_id or "").strip(),
                    DurableTaskState.lease_owner == normalized_worker,
                    DurableTaskState.status.in_(("leased", "processing")),
                )
                .limit(1)
            ).scalar_one_or_none()
            if row is None:
                return None
            row.status = str(status or "processing")[:32]
            row.active_dedupe_key_hash = self._active_dedupe_key_hash_for_row(
                row.dedupe_key_hash,
                row.status,
            )
            row.lease_expires_at = current_time + timedelta(seconds=max(1, min(int(lease_seconds or 60), 3600)))
            if progress is not None:
                row.progress = max(0, min(int(progress or 0), 100))
            if current_step is not None:
                row.current_step = sanitize_message(str(current_step or ""))[:500] or None
            if metadata is not None:
                prior = self._safe_json_loads(row.metadata_json, {})
                if not isinstance(prior, dict):
                    prior = {}
                prior.update(self._sanitize_task_metadata(metadata))
                row.metadata_json = self._safe_json_dumps(prior)
            row.updated_at = current_time
            session.flush()
            return self._durable_task_payload(row)

    def complete_claimed_durable_task_state(
        self,
        *,
        task_id: str,
        worker_id: str,
        current_step: str = "Task complete",
        metadata: Optional[Dict[str, Any]] = None,
        now: Optional[datetime] = None,
    ) -> Optional[Dict[str, Any]]:
        normalized_worker = sanitize_message(str(worker_id or "").strip())[:128]
        current_time = now or datetime.now()
        with self.session_scope() as session:
            row = session.execute(
                select(DurableTaskState)
                .where(
                    DurableTaskState.task_id == str(task_id or "").strip(),
                    DurableTaskState.lease_owner == normalized_worker,
                    DurableTaskState.status.in_(("leased", "processing")),
                )
                .limit(1)
            ).scalar_one_or_none()
            if row is None:
                return None
            if metadata is not None:
                prior = self._safe_json_loads(row.metadata_json, {})
                if not isinstance(prior, dict):
                    prior = {}
                prior.update(self._sanitize_task_metadata(metadata))
                row.metadata_json = self._safe_json_dumps(prior)
            row.status = "completed"
            row.active_dedupe_key_hash = None
            row.progress = 100
            row.current_step = sanitize_message(str(current_step or ""))[:500] or None
            row.completed_at = current_time
            row.lease_owner = None
            row.lease_expires_at = None
            row.updated_at = current_time
            session.flush()
            return self._durable_task_payload(row)

    def fail_claimed_durable_task_state(
        self,
        *,
        task_id: str,
        worker_id: str,
        error_code: str,
        error_summary: str,
        retryable: bool,
        current_step: str = "Task failed",
        metadata: Optional[Dict[str, Any]] = None,
        now: Optional[datetime] = None,
    ) -> Optional[Dict[str, Any]]:
        normalized_worker = sanitize_message(str(worker_id or "").strip())[:128]
        current_time = now or datetime.now()
        with self.session_scope() as session:
            row = session.execute(
                select(DurableTaskState)
                .where(
                    DurableTaskState.task_id == str(task_id or "").strip(),
                    DurableTaskState.lease_owner == normalized_worker,
                    DurableTaskState.status.in_(("leased", "processing")),
                )
                .limit(1)
            ).scalar_one_or_none()
            if row is None:
                return None
            if metadata is not None:
                prior = self._safe_json_loads(row.metadata_json, {})
                if not isinstance(prior, dict):
                    prior = {}
                prior.update(self._sanitize_task_metadata(metadata))
                row.metadata_json = self._safe_json_dumps(prior)
            attempts = max(0, int(row.attempt_count or 0))
            max_attempts = max(1, int(row.max_attempts or 1))
            should_retry = bool(retryable) and attempts < max_attempts
            row.status = "queued" if should_retry else "failed"
            row.active_dedupe_key_hash = self._active_dedupe_key_hash_for_row(
                row.dedupe_key_hash,
                row.status,
            )
            row.progress = 0 if should_retry else 100
            row.current_step = sanitize_message(str(current_step or ""))[:500] or None
            row.error_code = str(error_code or "worker_error")[:64] or None
            row.error_summary = self._sanitize_task_error_summary(error_summary)
            row.lease_owner = None
            row.lease_expires_at = None
            if not should_retry:
                row.failed_at = current_time
                row.completed_at = current_time
            row.updated_at = current_time
            session.flush()
            return self._durable_task_payload(row)

    def mark_durable_task_completed(
        self,
        *,
        task_id: str,
        owner_user_id: Optional[str] = None,
        current_step: str = "分析完成",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        now = datetime.now()
        return self.update_durable_task_state(
            task_id=task_id,
            owner_user_id=owner_user_id,
            status="completed",
            progress=100,
            current_step=current_step,
            metadata=metadata,
            completed_at=now,
        )

    def mark_durable_task_failed(
        self,
        *,
        task_id: str,
        owner_user_id: Optional[str] = None,
        error_code: Optional[str] = None,
        error_summary: Optional[str] = None,
        current_step: str = "分析失败",
    ) -> Optional[Dict[str, Any]]:
        now = datetime.now()
        return self.update_durable_task_state(
            task_id=task_id,
            owner_user_id=owner_user_id,
            status="failed",
            progress=100,
            current_step=current_step,
            failed_at=now,
            completed_at=now,
            error_code=error_code,
            error_summary=error_summary,
        )

    def get_durable_task_state(
        self,
        *,
        task_id: str,
        owner_user_id: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        normalized_task_id = str(task_id or "").strip()
        if not normalized_task_id:
            return None
        resolved_owner_id = self.require_user_id(owner_user_id)
        with self.get_session() as session:
            row = session.execute(
                select(DurableTaskState)
                .where(
                    DurableTaskState.task_id == normalized_task_id,
                    DurableTaskState.owner_user_id == resolved_owner_id,
                )
                .limit(1)
            ).scalar_one_or_none()
            return self._durable_task_payload(row) if row is not None else None

    def list_recent_durable_task_states(
        self,
        *,
        owner_user_id: Optional[str],
        status: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        resolved_owner_id = self.require_user_id(owner_user_id)
        safe_limit = max(1, min(int(limit or 20), 100))
        with self.get_session() as session:
            query = select(DurableTaskState).where(DurableTaskState.owner_user_id == resolved_owner_id)
            if status:
                query = query.where(DurableTaskState.status == str(status).strip())
            rows = session.execute(
                query.order_by(desc(DurableTaskState.created_at)).limit(safe_limit)
            ).scalars().all()
            return [self._durable_task_payload(row) for row in rows]

    @staticmethod
    def _sanitize_quota_metadata(value: Any) -> Dict[str, Any]:
        """Sanitize quota metadata and drop secret-like keys entirely."""
        def scrub(obj: Any) -> Any:
            if isinstance(obj, dict):
                cleaned: Dict[str, Any] = {}
                for key, item in obj.items():
                    key_text = str(key)
                    if is_sensitive_key(key_text):
                        continue
                    cleaned[key_text[:80]] = scrub(item)
                return cleaned
            if isinstance(obj, list):
                return [scrub(item) for item in obj[:50]]
            if isinstance(obj, tuple):
                return [scrub(item) for item in obj[:50]]
            if isinstance(obj, str):
                return sanitize_message(obj)[:500]
            return obj

        sanitized = sanitize_metadata(scrub(value or {}))
        return sanitized if isinstance(sanitized, dict) else {}

    @staticmethod
    def _quota_policy_payload(row: QuotaPolicyDefinition) -> Dict[str, Any]:
        return row.to_dict()

    def upsert_quota_policy(
        self,
        *,
        policy_key: str,
        scope_type: str,
        route_family: Optional[str] = None,
        provider: Optional[str] = None,
        model_tier: Optional[str] = None,
        daily_budget_units: Optional[int] = None,
        monthly_budget_units: Optional[int] = None,
        token_cap: Optional[int] = None,
        request_cap: Optional[int] = None,
        enabled: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        normalized_key = sanitize_message(str(policy_key or "").strip())[:128]
        normalized_scope = sanitize_message(str(scope_type or "").strip().lower())[:32]
        if not normalized_key:
            raise ValueError("policy_key is required")
        if normalized_scope not in {"global", "user", "route", "provider", "model_tier"}:
            raise ValueError("unsupported quota policy scope")

        def bounded_optional(value: Optional[int]) -> Optional[int]:
            if value is None:
                return None
            return max(0, int(value or 0))

        now = datetime.now()
        safe_metadata = self._sanitize_quota_metadata(metadata or {})
        with self.session_scope() as session:
            row = session.execute(
                select(QuotaPolicyDefinition)
                .where(QuotaPolicyDefinition.policy_key == normalized_key)
                .limit(1)
            ).scalar_one_or_none()
            if row is None:
                row = QuotaPolicyDefinition(policy_key=normalized_key, created_at=now)
                session.add(row)
            row.scope_type = normalized_scope
            row.route_family = sanitize_message(str(route_family or "").strip())[:64] or None
            row.provider = sanitize_message(str(provider or "").strip().lower())[:64] or None
            row.model_tier = sanitize_message(str(model_tier or "").strip().lower())[:64] or None
            row.daily_budget_units = bounded_optional(daily_budget_units)
            row.monthly_budget_units = bounded_optional(monthly_budget_units)
            row.token_cap = bounded_optional(token_cap)
            row.request_cap = bounded_optional(request_cap)
            row.enabled = bool(enabled)
            row.metadata_json = self._safe_json_dumps(safe_metadata)
            row.updated_at = now
            session.flush()
            return self._quota_policy_payload(row)

    def list_quota_policies(
        self,
        *,
        scope_type: Optional[str] = None,
        route_family: Optional[str] = None,
        provider: Optional[str] = None,
        model_tier: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        with self.get_session() as session:
            query = select(QuotaPolicyDefinition)
            if scope_type:
                query = query.where(QuotaPolicyDefinition.scope_type == str(scope_type).strip().lower())
            if route_family:
                query = query.where(
                    or_(
                        QuotaPolicyDefinition.route_family.is_(None),
                        QuotaPolicyDefinition.route_family == str(route_family).strip()[:64],
                    )
                )
            if provider:
                query = query.where(
                    or_(
                        QuotaPolicyDefinition.provider.is_(None),
                        QuotaPolicyDefinition.provider == str(provider).strip().lower()[:64],
                    )
                )
            if model_tier:
                query = query.where(
                    or_(
                        QuotaPolicyDefinition.model_tier.is_(None),
                        QuotaPolicyDefinition.model_tier == str(model_tier).strip().lower()[:64],
                    )
                )
            rows = session.execute(
                query.order_by(asc(QuotaPolicyDefinition.scope_type), asc(QuotaPolicyDefinition.policy_key))
            ).scalars().all()
            return [self._quota_policy_payload(row) for row in rows]

    @staticmethod
    def _normalize_cost_label(value: Optional[str], *, limit: int = 128, lowercase: bool = True) -> Optional[str]:
        text = sanitize_message(str(value or "").strip())
        if lowercase:
            text = text.lower()
        text = text[:limit]
        return text or None

    @staticmethod
    def _sanitize_llm_cost_metadata(value: Any) -> Dict[str, Any]:
        """Sanitize LLM cost metadata and drop prompts, payloads, sessions, and secrets."""
        blocked_key_fragments = (
            "api_key",
            "apikey",
            "auth",
            "cookie",
            "credential",
            "exception",
            "payload",
            "password",
            "private_key",
            "prompt",
            "raw",
            "request",
            "response",
            "secret",
            "session",
            "stack",
            "token",
            "trace",
            "traceback",
            "url",
            "webhook",
        )

        def scrub(obj: Any) -> Any:
            if isinstance(obj, dict):
                cleaned: Dict[str, Any] = {}
                for key, item in obj.items():
                    key_text = str(key)
                    key_lower = key_text.lower()
                    if is_sensitive_key(key_text) or any(fragment in key_lower for fragment in blocked_key_fragments):
                        continue
                    scrubbed = scrub(item)
                    if scrubbed is not None:
                        cleaned[key_text[:80]] = scrubbed
                return cleaned
            if isinstance(obj, list):
                values = [scrub(item) for item in obj[:50]]
                return [item for item in values if item is not None]
            if isinstance(obj, tuple):
                values = [scrub(item) for item in obj[:50]]
                return [item for item in values if item is not None]
            if isinstance(obj, str):
                text = obj.strip()
                lowered = text.lower()
                if (
                    "http://" in lowered
                    or "https://" in lowered
                    or "traceback (most recent call last)" in lowered
                    or "api_key" in lowered
                    or "token=" in lowered
                    or "cookie=" in lowered
                    or "session=" in lowered
                    or "authorization:" in lowered
                    or "bearer " in lowered
                ):
                    return None
                return sanitize_message(text)[:500]
            return obj

        sanitized = sanitize_metadata(scrub(value or {}))
        return sanitized if isinstance(sanitized, dict) else {}

    def upsert_model_pricing_policy(
        self,
        *,
        policy_key: str,
        provider: str,
        model: str,
        pricing_unit: str = "per_1m_tokens",
        input_price_per_1m: Any = 0,
        cached_input_price_per_1m: Any = None,
        output_price_per_1m: Any = 0,
        currency: str = "USD",
        effective_from: Optional[datetime] = None,
        effective_until: Optional[datetime] = None,
        source_label: Optional[str] = None,
        source_url: Optional[str] = None,
        active: bool = True,
        metadata_json: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        normalized_key = self._normalize_cost_label(policy_key, limit=160, lowercase=False)
        provider_key = self._normalize_cost_label(provider, limit=64)
        model_key = self._normalize_cost_label(model, limit=128)
        unit_key = self._normalize_cost_label(pricing_unit, limit=32) or "per_1m_tokens"
        currency_key = (self._normalize_cost_label(currency, limit=8, lowercase=False) or "USD").upper()
        if not normalized_key:
            raise ValueError("policy_key is required")
        if not provider_key or not model_key:
            raise ValueError("provider and model are required")
        now = datetime.now()
        effective_start = effective_from or now
        raw_metadata = metadata if metadata is not None else metadata_json
        safe_metadata = self._sanitize_llm_cost_metadata(raw_metadata or {})
        with self.session_scope() as session:
            row = session.execute(
                select(ModelPricingPolicy)
                .where(ModelPricingPolicy.policy_key == normalized_key)
                .limit(1)
            ).scalar_one_or_none()
            if row is None:
                row = ModelPricingPolicy(policy_key=normalized_key, created_at=now)
                session.add(row)
            row.provider = provider_key
            row.model = model_key
            row.pricing_unit = unit_key
            row.input_price_per_1m = input_price_per_1m or 0
            row.cached_input_price_per_1m = cached_input_price_per_1m
            row.output_price_per_1m = output_price_per_1m or 0
            row.currency = currency_key
            row.effective_from = effective_start
            row.effective_until = effective_until
            row.source_label = sanitize_message(str(source_label or "").strip())[:128] or None
            row.source_url = sanitize_message(str(source_url or "").strip())[:500] or None
            row.active = bool(active)
            row.metadata_json = self._safe_json_dumps(safe_metadata)
            row.updated_at = now
            session.flush()
            return row.to_dict()

    def get_model_pricing_policy(
        self,
        *,
        provider: str,
        model: str,
        at: Optional[datetime] = None,
        include_inactive: bool = False,
    ) -> Optional[ModelPricingPolicy]:
        provider_key = self._normalize_cost_label(provider, limit=64)
        model_key = self._normalize_cost_label(model, limit=128)
        if not provider_key or not model_key:
            return None
        effective_time = at or datetime.now()
        with self.get_session() as session:
            query = (
                select(ModelPricingPolicy)
                .where(
                    ModelPricingPolicy.provider == provider_key,
                    ModelPricingPolicy.model == model_key,
                    ModelPricingPolicy.effective_from <= effective_time,
                    or_(ModelPricingPolicy.effective_until.is_(None), ModelPricingPolicy.effective_until > effective_time),
                )
                .order_by(desc(ModelPricingPolicy.active), desc(ModelPricingPolicy.effective_from), desc(ModelPricingPolicy.updated_at))
                .limit(1)
            )
            if not include_inactive:
                query = query.where(ModelPricingPolicy.active.is_(True))
            row = session.execute(query).scalar_one_or_none()
            if row is None:
                return None
            session.expunge(row)
            return row

    @staticmethod
    def _llm_cost_identity_filters(
        *,
        owner_user_id: Optional[str],
        guest_bucket_hash: Optional[str],
        request_hash: str,
    ) -> Tuple[Any, ...]:
        filters: List[Any] = [LLMCostLedger.request_hash == request_hash]
        if owner_user_id is None:
            filters.append(LLMCostLedger.owner_user_id.is_(None))
        else:
            filters.append(LLMCostLedger.owner_user_id == owner_user_id)
        if guest_bucket_hash is None:
            filters.append(LLMCostLedger.guest_bucket_hash.is_(None))
        else:
            filters.append(LLMCostLedger.guest_bucket_hash == guest_bucket_hash)
        return tuple(filters)

    def get_llm_cost_ledger_by_request_identity(
        self,
        *,
        owner_user_id: Optional[str] = None,
        guest_bucket_hash: Optional[str] = None,
        request_hash: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        request_key = self._normalize_cost_label(request_hash, limit=128, lowercase=False)
        if not request_key:
            return None
        owner_key = self._normalize_cost_label(owner_user_id, limit=64, lowercase=False)
        guest_key = self._normalize_cost_label(guest_bucket_hash, limit=128, lowercase=False)
        with self.get_session() as session:
            row = session.execute(
                select(LLMCostLedger)
                .where(
                    *self._llm_cost_identity_filters(
                        owner_user_id=owner_key,
                        guest_bucket_hash=guest_key,
                        request_hash=request_key,
                    )
                )
                .order_by(asc(LLMCostLedger.id))
                .limit(1)
            ).scalar_one_or_none()
            return row.to_dict() if row is not None else None

    def record_llm_cost_ledger(self, **kwargs: Any) -> Dict[str, Any]:
        now = kwargs.get("created_at") or datetime.now()
        metadata = self._sanitize_llm_cost_metadata(kwargs.get("metadata") or {})
        snapshot = self._sanitize_llm_cost_metadata(kwargs.get("pricing_snapshot") or {})
        row = LLMCostLedger(
            ledger_id=str(kwargs.get("ledger_id") or "")[:64],
            owner_user_id=self._normalize_cost_label(kwargs.get("owner_user_id"), limit=64, lowercase=False),
            guest_bucket_hash=self._normalize_cost_label(kwargs.get("guest_bucket_hash"), limit=128, lowercase=False),
            route_family=self._normalize_cost_label(kwargs.get("route_family"), limit=64) or "analysis",
            call_type=self._normalize_cost_label(kwargs.get("call_type"), limit=64) or "analysis",
            provider=self._normalize_cost_label(kwargs.get("provider"), limit=64) or "unknown",
            model=self._normalize_cost_label(kwargs.get("model"), limit=128) or "unknown",
            prompt_tokens=max(0, int(kwargs.get("prompt_tokens") or 0)),
            cached_input_tokens=max(0, int(kwargs.get("cached_input_tokens") or 0)),
            cache_miss_input_tokens=max(0, int(kwargs.get("cache_miss_input_tokens") or 0)),
            completion_tokens=max(0, int(kwargs.get("completion_tokens") or 0)),
            total_tokens=max(0, int(kwargs.get("total_tokens") or 0)),
            input_cost_usd=kwargs.get("input_cost_usd") or 0,
            cached_input_cost_usd=kwargs.get("cached_input_cost_usd") or 0,
            output_cost_usd=kwargs.get("output_cost_usd") or 0,
            total_cost_usd=kwargs.get("total_cost_usd") or 0,
            pricing_policy_key=self._normalize_cost_label(kwargs.get("pricing_policy_key"), limit=160, lowercase=False),
            pricing_snapshot_json=self._safe_json_dumps(snapshot),
            quota_reservation_id=self._normalize_cost_label(kwargs.get("quota_reservation_id"), limit=64, lowercase=False),
            request_hash=self._normalize_cost_label(kwargs.get("request_hash"), limit=128, lowercase=False),
            status=self._normalize_cost_label(kwargs.get("status"), limit=32) or "ok",
            metadata_json=self._safe_json_dumps(metadata),
            created_at=now,
        )
        if not row.ledger_id:
            raise ValueError("ledger_id is required")
        with self.session_scope() as session:
            if row.request_hash:
                existing = session.execute(
                    select(LLMCostLedger)
                    .where(
                        *self._llm_cost_identity_filters(
                            owner_user_id=row.owner_user_id,
                            guest_bucket_hash=row.guest_bucket_hash,
                            request_hash=row.request_hash,
                        )
                    )
                    .order_by(asc(LLMCostLedger.id))
                    .limit(1)
                ).scalar_one_or_none()
                if existing is not None:
                    return existing.to_dict()
            session.add(row)
            session.flush()
            return row.to_dict()

    @staticmethod
    def _decimal_sum_label(value: Any) -> str:
        text = f"{float(value or 0):.6f}"
        return text.rstrip("0").rstrip(".") if "." in text else text

    def get_llm_cost_ledger_summary(
        self,
        *,
        from_dt: datetime,
        to_dt: datetime,
        limit: int = 50,
    ) -> Dict[str, Any]:
        safe_limit = max(1, min(int(limit or 50), 200))
        with self.session_scope() as session:
            base_filter = and_(LLMCostLedger.created_at >= from_dt, LLMCostLedger.created_at <= to_dt)
            total = session.execute(
                select(
                    func.count(LLMCostLedger.id).label("calls"),
                    func.coalesce(func.sum(LLMCostLedger.prompt_tokens), 0).label("prompt_tokens"),
                    func.coalesce(func.sum(LLMCostLedger.cached_input_tokens), 0).label("cached_input_tokens"),
                    func.coalesce(func.sum(LLMCostLedger.completion_tokens), 0).label("completion_tokens"),
                    func.coalesce(func.sum(LLMCostLedger.total_tokens), 0).label("total_tokens"),
                    func.coalesce(func.sum(LLMCostLedger.total_cost_usd), 0).label("total_cost_usd"),
                ).where(base_filter)
            ).one()

            def grouped(*columns):
                rows = session.execute(
                    select(
                        *columns,
                        func.count(LLMCostLedger.id).label("calls"),
                        func.coalesce(func.sum(LLMCostLedger.total_tokens), 0).label("total_tokens"),
                        func.coalesce(func.sum(LLMCostLedger.total_cost_usd), 0).label("total_cost_usd"),
                    )
                    .where(base_filter)
                    .group_by(*columns)
                    .order_by(desc(func.sum(LLMCostLedger.total_cost_usd)), desc(func.sum(LLMCostLedger.total_tokens)))
                    .limit(safe_limit)
                ).all()
                return rows

            by_user_rows = grouped(LLMCostLedger.owner_user_id)
            by_provider_model_rows = grouped(LLMCostLedger.provider, LLMCostLedger.model)
            by_route_rows = grouped(LLMCostLedger.route_family)

        return {
            "total": {
                "calls": int(total.calls or 0),
                "prompt_tokens": int(total.prompt_tokens or 0),
                "cached_input_tokens": int(total.cached_input_tokens or 0),
                "completion_tokens": int(total.completion_tokens or 0),
                "total_tokens": int(total.total_tokens or 0),
                "total_cost_usd": self._decimal_sum_label(total.total_cost_usd),
            },
            "by_user": [
                {
                    "owner_user_id": row[0] or "guest_or_unknown",
                    "calls": int(row.calls or 0),
                    "total_tokens": int(row.total_tokens or 0),
                    "total_cost_usd": self._decimal_sum_label(row.total_cost_usd),
                }
                for row in by_user_rows
            ],
            "by_provider_model": [
                {
                    "provider": row[0],
                    "model": row[1],
                    "provider_model": f"{row[0]}|{row[1]}",
                    "calls": int(row.calls or 0),
                    "total_tokens": int(row.total_tokens or 0),
                    "total_cost_usd": self._decimal_sum_label(row.total_cost_usd),
                }
                for row in by_provider_model_rows
            ],
            "by_route_family": [
                {
                    "route_family": row[0],
                    "calls": int(row.calls or 0),
                    "total_tokens": int(row.total_tokens or 0),
                    "total_cost_usd": self._decimal_sum_label(row.total_cost_usd),
                }
                for row in by_route_rows
            ],
        }

    _PROVIDER_CIRCUIT_STATES = {
        "closed",
        "open",
        "half_open",
        "degraded_cache_only",
        "disabled_by_operator",
        "provider_quota_depleted",
    }
    _PROVIDER_CIRCUIT_REASONS = {
        "timeout",
        "provider_429",
        "provider_403",
        "provider_5xx",
        "malformed_payload",
        "insufficient_payload",
        "auth_or_key_invalid",
        "network_error",
        "quota_policy_block",
        "operator_disabled",
        "synthetic_test",
        "recovered",
    }

    @staticmethod
    def _normalize_provider_label(value: Any, *, required: bool = True) -> Optional[str]:
        text = sanitize_message(str(value or "").strip().lower())[:64]
        if required and not text:
            raise ValueError("provider is required")
        return text or None

    @staticmethod
    def _normalize_provider_dimension(value: Any, limit: int = 64) -> Optional[str]:
        text = sanitize_message(str(value or "").strip().lower())[:limit]
        return text or None

    @staticmethod
    def _optional_equals(column, value: Optional[str]):
        return column.is_(None) if value is None else column == value

    @staticmethod
    def _sanitize_provider_circuit_metadata(value: Any) -> Dict[str, Any]:
        """Sanitize provider circuit metadata and drop raw payload/secret-like keys."""
        blocked_key_fragments = (
            "api_key",
            "apikey",
            "auth",
            "cookie",
            "credential",
            "exception",
            "payload",
            "password",
            "private_key",
            "query",
            "request",
            "response",
            "secret",
            "session",
            "stack",
            "token",
            "traceback",
            "url",
            "webhook",
        )

        def scrub(obj: Any) -> Any:
            if isinstance(obj, dict):
                cleaned: Dict[str, Any] = {}
                for key, item in obj.items():
                    key_text = str(key)
                    key_lower = key_text.lower()
                    if is_sensitive_key(key_text) or any(fragment in key_lower for fragment in blocked_key_fragments):
                        continue
                    scrubbed = scrub(item)
                    if scrubbed is not None:
                        cleaned[key_text[:80]] = scrubbed
                return cleaned
            if isinstance(obj, list):
                values = [scrub(item) for item in obj[:50]]
                return [item for item in values if item is not None]
            if isinstance(obj, tuple):
                values = [scrub(item) for item in obj[:50]]
                return [item for item in values if item is not None]
            if isinstance(obj, str):
                text = obj.strip()
                lowered = text.lower()
                if (
                    "http://" in lowered
                    or "https://" in lowered
                    or "traceback (most recent call last)" in lowered
                    or "api_key" in lowered
                    or "token=" in lowered
                    or "cookie=" in lowered
                    or "session=" in lowered
                ):
                    return None
                return sanitize_message(text)[:500]
            return obj

        sanitized = sanitize_metadata(scrub(value or {}))
        return sanitized if isinstance(sanitized, dict) else {}

    @staticmethod
    def _provider_circuit_state_payload(row: ProviderCircuitState) -> Dict[str, Any]:
        return row.to_dict()

    @staticmethod
    def _provider_circuit_event_payload(row: ProviderCircuitEvent) -> Dict[str, Any]:
        return row.to_dict()

    @staticmethod
    def _provider_quota_window_payload(row: ProviderQuotaWindow) -> Dict[str, Any]:
        return row.to_dict()

    @staticmethod
    def _provider_probe_event_payload(row: ProviderProbeEvent) -> Dict[str, Any]:
        return row.to_dict()

    def _provider_circuit_state_query(
        self,
        *,
        scope_type: str,
        owner_user_id: Optional[str],
        guest_bucket_hash: Optional[str],
        provider: str,
        provider_category: Optional[str],
        route_family: Optional[str],
    ):
        return select(ProviderCircuitState).where(
            ProviderCircuitState.scope_type == scope_type,
            self._optional_equals(ProviderCircuitState.owner_user_id, owner_user_id),
            self._optional_equals(ProviderCircuitState.guest_bucket_hash, guest_bucket_hash),
            ProviderCircuitState.provider == provider,
            self._optional_equals(ProviderCircuitState.provider_category, provider_category),
            self._optional_equals(ProviderCircuitState.route_family, route_family),
        )

    def upsert_provider_circuit_state(
        self,
        *,
        provider: str,
        state: str,
        scope_type: str = "provider",
        provider_category: Optional[str] = None,
        route_family: Optional[str] = None,
        owner_user_id: Optional[str] = None,
        guest_bucket_hash: Optional[str] = None,
        reason_bucket: Optional[str] = None,
        cooldown_until: Optional[datetime] = None,
        half_open_started_at: Optional[datetime] = None,
        half_open_sample_limit: Optional[int] = None,
        half_open_sample_count: Optional[int] = None,
        success_sample_count: Optional[int] = None,
        failure_sample_count: Optional[int] = None,
        failure_count: Optional[int] = None,
        success_count: Optional[int] = None,
        operator_action_ref: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        normalized_provider = self._normalize_provider_label(provider)
        normalized_scope = self._normalize_provider_dimension(scope_type, 32) or "provider"
        normalized_state = self._normalize_provider_dimension(state, 32) or "closed"
        if normalized_state not in self._PROVIDER_CIRCUIT_STATES:
            raise ValueError("unsupported provider circuit state")
        normalized_reason = self._normalize_provider_dimension(reason_bucket, 64)
        if normalized_reason and normalized_reason not in self._PROVIDER_CIRCUIT_REASONS:
            raise ValueError("unsupported provider circuit reason bucket")
        normalized_category = self._normalize_provider_dimension(provider_category, 64)
        normalized_route = self._normalize_provider_dimension(route_family, 64)
        normalized_owner = sanitize_message(str(owner_user_id or "").strip())[:64] or None
        normalized_guest = sanitize_message(str(guest_bucket_hash or "").strip())[:128] or None
        current_time = now or datetime.now()
        safe_metadata = self._sanitize_provider_circuit_metadata(metadata or {})
        safe_operator_ref = sanitize_message(str(operator_action_ref or "").strip())[:128] or None

        with self.session_scope() as session:
            row = session.execute(
                self._provider_circuit_state_query(
                    scope_type=normalized_scope,
                    owner_user_id=normalized_owner,
                    guest_bucket_hash=normalized_guest,
                    provider=normalized_provider,
                    provider_category=normalized_category,
                    route_family=normalized_route,
                ).limit(1)
            ).scalar_one_or_none()
            if row is None:
                row = ProviderCircuitState(
                    scope_type=normalized_scope,
                    owner_user_id=normalized_owner,
                    guest_bucket_hash=normalized_guest,
                    provider=normalized_provider,
                    provider_category=normalized_category,
                    route_family=normalized_route,
                    created_at=current_time,
                )
                session.add(row)
            previous = row.state
            row.previous_state = previous if previous and previous != normalized_state else row.previous_state
            row.state = normalized_state
            row.reason_bucket = normalized_reason
            row.cooldown_until = cooldown_until
            row.half_open_started_at = half_open_started_at
            row.half_open_sample_limit = max(0, int(half_open_sample_limit or 0)) if half_open_sample_limit is not None else int(row.half_open_sample_limit or 0)
            row.half_open_sample_count = max(0, int(half_open_sample_count or 0)) if half_open_sample_count is not None else int(row.half_open_sample_count or 0)
            row.success_sample_count = max(0, int(success_sample_count or 0)) if success_sample_count is not None else int(row.success_sample_count or 0)
            row.failure_sample_count = max(0, int(failure_sample_count or 0)) if failure_sample_count is not None else int(row.failure_sample_count or 0)
            row.failure_count = max(0, int(failure_count or 0)) if failure_count is not None else int(row.failure_count or 0)
            row.success_count = max(0, int(success_count or 0)) if success_count is not None else int(row.success_count or 0)
            row.opened_at = current_time if normalized_state in {"open", "degraded_cache_only", "provider_quota_depleted"} and row.opened_at is None else row.opened_at
            if normalized_state == "closed":
                row.opened_at = None
                row.cooldown_until = None
            row.operator_action_ref = safe_operator_ref
            row.metadata_json = self._safe_json_dumps(safe_metadata)
            row.updated_at = current_time
            session.flush()
            return self._provider_circuit_state_payload(row)

    def get_provider_circuit_state(
        self,
        *,
        provider: str,
        scope_type: str = "provider",
        provider_category: Optional[str] = None,
        route_family: Optional[str] = None,
        owner_user_id: Optional[str] = None,
        guest_bucket_hash: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        normalized_provider = self._normalize_provider_label(provider)
        with self.get_session() as session:
            row = session.execute(
                self._provider_circuit_state_query(
                    scope_type=self._normalize_provider_dimension(scope_type, 32) or "provider",
                    owner_user_id=sanitize_message(str(owner_user_id or "").strip())[:64] or None,
                    guest_bucket_hash=sanitize_message(str(guest_bucket_hash or "").strip())[:128] or None,
                    provider=normalized_provider,
                    provider_category=self._normalize_provider_dimension(provider_category, 64),
                    route_family=self._normalize_provider_dimension(route_family, 64),
                ).limit(1)
            ).scalar_one_or_none()
            return self._provider_circuit_state_payload(row) if row is not None else None

    def append_provider_circuit_event(
        self,
        *,
        provider: str,
        event_type: str,
        from_state: Optional[str] = None,
        to_state: Optional[str] = None,
        state_id: Optional[int] = None,
        reason_bucket: Optional[str] = None,
        provider_category: Optional[str] = None,
        route_family: Optional[str] = None,
        owner_user_id: Optional[str] = None,
        guest_bucket_hash: Optional[str] = None,
        request_count_bucket: Optional[str] = None,
        duration_bucket_ms: Optional[int] = None,
        failure_count_bucket: Optional[str] = None,
        quota_window_start: Optional[datetime] = None,
        quota_window_end: Optional[datetime] = None,
        operator_action_ref: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        normalized_provider = self._normalize_provider_label(provider)
        normalized_reason = self._normalize_provider_dimension(reason_bucket, 64)
        if normalized_reason and normalized_reason not in self._PROVIDER_CIRCUIT_REASONS:
            raise ValueError("unsupported provider circuit reason bucket")
        current_time = created_at or datetime.now()
        row = ProviderCircuitEvent(
            state_id=state_id,
            event_type=self._normalize_provider_dimension(event_type, 32) or "state_transition",
            from_state=self._normalize_provider_dimension(from_state, 32),
            to_state=self._normalize_provider_dimension(to_state, 32),
            reason_bucket=normalized_reason,
            owner_user_id=sanitize_message(str(owner_user_id or "").strip())[:64] or None,
            guest_bucket_hash=sanitize_message(str(guest_bucket_hash or "").strip())[:128] or None,
            provider=normalized_provider,
            provider_category=self._normalize_provider_dimension(provider_category, 64),
            route_family=self._normalize_provider_dimension(route_family, 64),
            request_count_bucket=sanitize_message(str(request_count_bucket or "").strip())[:32] or None,
            duration_bucket_ms=max(0, int(duration_bucket_ms or 0)) if duration_bucket_ms is not None else None,
            failure_count_bucket=sanitize_message(str(failure_count_bucket or "").strip())[:32] or None,
            quota_window_start=quota_window_start,
            quota_window_end=quota_window_end,
            operator_action_ref=sanitize_message(str(operator_action_ref or "").strip())[:128] or None,
            metadata_json=self._safe_json_dumps(self._sanitize_provider_circuit_metadata(metadata or {})),
            created_at=current_time,
        )
        with self.session_scope() as session:
            session.add(row)
            session.flush()
            return self._provider_circuit_event_payload(row)

    def transition_provider_circuit_state(
        self,
        *,
        provider: str,
        to_state: str,
        scope_type: str = "provider",
        provider_category: Optional[str] = None,
        route_family: Optional[str] = None,
        owner_user_id: Optional[str] = None,
        guest_bucket_hash: Optional[str] = None,
        reason_bucket: Optional[str] = None,
        cooldown_until: Optional[datetime] = None,
        half_open_started_at: Optional[datetime] = None,
        half_open_sample_limit: Optional[int] = None,
        half_open_sample_count: Optional[int] = None,
        success_sample_count: Optional[int] = None,
        failure_sample_count: Optional[int] = None,
        failure_count: Optional[int] = None,
        success_count: Optional[int] = None,
        operator_action_ref: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        current = self.get_provider_circuit_state(
            provider=provider,
            scope_type=scope_type,
            provider_category=provider_category,
            route_family=route_family,
            owner_user_id=owner_user_id,
            guest_bucket_hash=guest_bucket_hash,
        )
        from_state = str((current or {}).get("state") or "closed")
        state = self.upsert_provider_circuit_state(
            provider=provider,
            state=to_state,
            scope_type=scope_type,
            provider_category=provider_category,
            route_family=route_family,
            owner_user_id=owner_user_id,
            guest_bucket_hash=guest_bucket_hash,
            reason_bucket=reason_bucket,
            cooldown_until=cooldown_until,
            half_open_started_at=half_open_started_at,
            half_open_sample_limit=half_open_sample_limit,
            half_open_sample_count=half_open_sample_count,
            success_sample_count=success_sample_count,
            failure_sample_count=failure_sample_count,
            failure_count=failure_count,
            success_count=success_count,
            operator_action_ref=operator_action_ref,
            metadata=metadata,
            now=now,
        )
        event = self.append_provider_circuit_event(
            provider=provider,
            event_type="state_transition",
            from_state=from_state,
            to_state=to_state,
            state_id=int(state["id"]),
            reason_bucket=reason_bucket,
            provider_category=provider_category,
            route_family=route_family,
            owner_user_id=owner_user_id,
            guest_bucket_hash=guest_bucket_hash,
            operator_action_ref=operator_action_ref,
            metadata=metadata,
            created_at=now,
        )
        with self.session_scope() as session:
            row = session.get(ProviderCircuitState, int(state["id"]))
            if row is not None:
                row.last_transition_event_id = int(event["id"])
                row.previous_state = from_state
                row.updated_at = now or datetime.now()
                session.flush()
                state = self._provider_circuit_state_payload(row)
        state["transition_event"] = event
        return state

    def list_current_provider_circuits(
        self,
        *,
        provider: Optional[str] = None,
        state: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        safe_limit = max(1, min(int(limit or 100), 500))
        with self.get_session() as session:
            query = select(ProviderCircuitState)
            if provider:
                query = query.where(ProviderCircuitState.provider == self._normalize_provider_label(provider))
            if state:
                query = query.where(ProviderCircuitState.state == self._normalize_provider_dimension(state, 32))
            rows = session.execute(
                query.order_by(desc(ProviderCircuitState.updated_at), asc(ProviderCircuitState.provider)).limit(safe_limit)
            ).scalars().all()
            return [self._provider_circuit_state_payload(row) for row in rows]

    def update_provider_quota_window_counters(
        self,
        *,
        provider: str,
        window_type: str,
        window_start: datetime,
        window_end: datetime,
        policy_key: Optional[str] = None,
        provider_category: Optional[str] = None,
        route_family: Optional[str] = None,
        owner_user_id: Optional[str] = None,
        guest_bucket_hash: Optional[str] = None,
        request_delta: int = 0,
        reserved_units_delta: int = 0,
        consumed_units_delta: int = 0,
        released_units_delta: int = 0,
        rejected_delta: int = 0,
        success_delta: int = 0,
        failure_delta: int = 0,
        timeout_delta: int = 0,
        provider_429_delta: int = 0,
        provider_403_delta: int = 0,
        fallback_delta: int = 0,
        probe_delta: int = 0,
        cache_only_delta: int = 0,
        stale_served_delta: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        normalized_provider = self._normalize_provider_label(provider)
        normalized_category = self._normalize_provider_dimension(provider_category, 64)
        normalized_route = self._normalize_provider_dimension(route_family, 64)
        normalized_owner = sanitize_message(str(owner_user_id or "").strip())[:64] or None
        normalized_guest = sanitize_message(str(guest_bucket_hash or "").strip())[:128] or None
        normalized_window_type = self._normalize_provider_dimension(window_type, 16) or "custom"
        safe_policy_key = sanitize_message(str(policy_key or "").strip())[:128] or None
        safe_metadata = self._sanitize_provider_circuit_metadata(metadata or {})
        now = datetime.now()

        def add_count(current: Any, delta: int) -> int:
            return max(0, int(current or 0) + int(delta or 0))

        with self.session_scope() as session:
            row = session.execute(
                select(ProviderQuotaWindow)
                .where(
                    self._optional_equals(ProviderQuotaWindow.policy_key, safe_policy_key),
                    self._optional_equals(ProviderQuotaWindow.owner_user_id, normalized_owner),
                    self._optional_equals(ProviderQuotaWindow.guest_bucket_hash, normalized_guest),
                    ProviderQuotaWindow.provider == normalized_provider,
                    self._optional_equals(ProviderQuotaWindow.provider_category, normalized_category),
                    self._optional_equals(ProviderQuotaWindow.route_family, normalized_route),
                    ProviderQuotaWindow.window_type == normalized_window_type,
                    ProviderQuotaWindow.window_start == window_start,
                    ProviderQuotaWindow.window_end == window_end,
                )
                .limit(1)
            ).scalar_one_or_none()
            if row is None:
                row = ProviderQuotaWindow(
                    policy_key=safe_policy_key,
                    owner_user_id=normalized_owner,
                    guest_bucket_hash=normalized_guest,
                    provider=normalized_provider,
                    provider_category=normalized_category,
                    route_family=normalized_route,
                    window_type=normalized_window_type,
                    window_start=window_start,
                    window_end=window_end,
                    created_at=now,
                )
                session.add(row)
            row.request_count = add_count(row.request_count, request_delta)
            row.reserved_units = add_count(row.reserved_units, reserved_units_delta)
            row.consumed_units = add_count(row.consumed_units, consumed_units_delta)
            row.released_units = add_count(row.released_units, released_units_delta)
            row.rejected_count = add_count(row.rejected_count, rejected_delta)
            row.success_count = add_count(row.success_count, success_delta)
            row.failure_count = add_count(row.failure_count, failure_delta)
            row.timeout_count = add_count(row.timeout_count, timeout_delta)
            row.provider_429_count = add_count(row.provider_429_count, provider_429_delta)
            row.provider_403_count = add_count(row.provider_403_count, provider_403_delta)
            row.fallback_count = add_count(row.fallback_count, fallback_delta)
            row.probe_count = add_count(row.probe_count, probe_delta)
            row.cache_only_count = add_count(row.cache_only_count, cache_only_delta)
            row.stale_served_count = add_count(row.stale_served_count, stale_served_delta)
            if metadata is not None:
                prior = self._safe_json_loads(row.metadata_json, {})
                if not isinstance(prior, dict):
                    prior = {}
                prior.update(safe_metadata)
                row.metadata_json = self._safe_json_dumps(prior)
            row.updated_at = now
            session.flush()
            return self._provider_quota_window_payload(row)

    def record_provider_probe_event(
        self,
        *,
        provider: str,
        probe_type: str,
        result_bucket: str,
        probe_source: str = "synthetic",
        actor_user_id: Optional[str] = None,
        provider_category: Optional[str] = None,
        route_family: Optional[str] = None,
        state_id: Optional[int] = None,
        duration_bucket_ms: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        normalized_result = self._normalize_provider_dimension(result_bucket, 64) or "success"
        if normalized_result not in self._PROVIDER_CIRCUIT_REASONS and normalized_result != "success":
            raise ValueError("unsupported provider probe result bucket")
        row = ProviderProbeEvent(
            probe_type=self._normalize_provider_dimension(probe_type, 32) or "synthetic_fixture",
            probe_source=self._normalize_provider_dimension(probe_source, 32) or "synthetic",
            actor_user_id=sanitize_message(str(actor_user_id or "").strip())[:64] or None,
            provider=self._normalize_provider_label(provider),
            provider_category=self._normalize_provider_dimension(provider_category, 64),
            route_family=self._normalize_provider_dimension(route_family, 64),
            state_id=state_id,
            result_bucket=normalized_result,
            duration_bucket_ms=max(0, int(duration_bucket_ms or 0)) if duration_bucket_ms is not None else None,
            metadata_json=self._safe_json_dumps(self._sanitize_provider_circuit_metadata(metadata or {})),
            created_at=created_at or datetime.now(),
        )
        with self.session_scope() as session:
            session.add(row)
            session.flush()
            return self._provider_probe_event_payload(row)

    def get_app_user(self, user_id: str) -> Optional[AppUser]:
        normalized = str(user_id or "").strip()
        if not normalized:
            return None
        if self._phase_a_enabled and self._phase_a_store is not None:
            row = self._phase_a_store.get_app_user(normalized)
            if row is not None:
                return row
            legacy_row = self._sqlite_get_app_user(normalized)
            if legacy_row is None:
                return None
            return self._sync_phase_a_user_from_legacy(legacy_row)
        return self._sqlite_get_app_user(normalized)

    def get_app_user_by_username(self, username: str) -> Optional[AppUser]:
        normalized = str(username or "").strip()
        if not normalized:
            return None
        if self._phase_a_enabled and self._phase_a_store is not None:
            row = self._phase_a_store.get_app_user_by_username(normalized)
            if row is not None:
                return row
            legacy_row = self._sqlite_get_app_user_by_username(normalized)
            if legacy_row is None:
                return None
            return self._sync_phase_a_user_from_legacy(legacy_row)
        return self._sqlite_get_app_user_by_username(normalized)

    def list_app_users(self) -> List[Any]:
        legacy_rows = self._sqlite_list_app_users()
        if self._phase_a_enabled and self._phase_a_store is not None:
            rows_by_id: Dict[str, Any] = {
                str(row.id): row
                for row in self._phase_a_store.list_app_users()
                if str(getattr(row, "id", "") or "").strip()
            }
            for legacy_row in legacy_rows:
                user_id = str(getattr(legacy_row, "id", "") or "").strip()
                if user_id and user_id not in rows_by_id:
                    rows_by_id[user_id] = self._sync_phase_a_user_from_legacy(legacy_row) or legacy_row
            return sorted(
                rows_by_id.values(),
                key=lambda row: (getattr(row, "created_at", None) or datetime.min, str(getattr(row, "id", ""))),
                reverse=True,
            )
        return legacy_rows

    def list_admin_roles(self) -> List[str]:
        with self.get_session() as session:
            return [
                str(value)
                for value in session.execute(
                    select(AdminRole.role_key).order_by(asc(AdminRole.role_key))
                ).scalars().all()
                if str(value or "").strip()
            ]

    def list_admin_role_capabilities(self, role_key: str) -> List[str]:
        normalized_role = str(role_key or "").strip()
        if not normalized_role:
            return []
        with self.get_session() as session:
            return [
                str(value)
                for value in session.execute(
                    select(AdminRoleCapability.capability)
                    .where(AdminRoleCapability.role_key == normalized_role)
                    .order_by(asc(AdminRoleCapability.capability))
                ).scalars().all()
                if str(value or "").strip()
            ]

    def list_admin_user_roles(self, user_id: str) -> List[str]:
        normalized_user_id = str(user_id or "").strip()
        if not normalized_user_id:
            return []
        with self.get_session() as session:
            return [
                str(value)
                for value in session.execute(
                    select(AdminUserRole.role_key)
                    .where(AdminUserRole.user_id == normalized_user_id)
                    .order_by(asc(AdminUserRole.role_key))
                ).scalars().all()
                if str(value or "").strip()
            ]

    def list_admin_capabilities_for_user(self, user_id: str) -> List[str]:
        role_keys = self.list_admin_user_roles(user_id)
        if not role_keys:
            return []
        with self.get_session() as session:
            return [
                str(value)
                for value in session.execute(
                    select(AdminRoleCapability.capability)
                    .where(AdminRoleCapability.role_key.in_(role_keys))
                    .distinct()
                    .order_by(asc(AdminRoleCapability.capability))
                ).scalars().all()
                if str(value or "").strip()
            ]

    def list_app_user_sessions(self, user_id: Optional[str] = None) -> List[Any]:
        legacy_rows = self._sqlite_list_app_user_sessions(user_id)
        if self._phase_a_enabled and self._phase_a_store is not None:
            rows_by_id: Dict[str, Any] = {
                str(row.session_id): row
                for row in self._phase_a_store.list_app_user_sessions(user_id)
                if str(getattr(row, "session_id", "") or "").strip()
            }
            for legacy_row in legacy_rows:
                session_id = str(getattr(legacy_row, "session_id", "") or "").strip()
                if session_id and session_id not in rows_by_id:
                    rows_by_id[session_id] = self._sync_phase_a_session_from_legacy(legacy_row) or legacy_row
            return sorted(
                rows_by_id.values(),
                key=lambda row: (getattr(row, "created_at", None) or datetime.min, str(getattr(row, "session_id", ""))),
                reverse=True,
            )
        return legacy_rows

    def create_or_update_app_user(
        self,
        *,
        user_id: str,
        username: str,
        role: str = ROLE_USER,
        display_name: Optional[str] = None,
        password_hash: Optional[str] = None,
        mfa_enabled: Optional[bool] = None,
        mfa_secret_ref: Optional[str] = None,
        mfa_recovery_codes_hash: Optional[str] = None,
        mfa_created_at: Optional[datetime] = None,
        mfa_enabled_at: Optional[datetime] = None,
        mfa_last_verified_at: Optional[datetime] = None,
        is_active: bool = True,
    ) -> AppUser:
        normalized_id = str(user_id or "").strip()
        normalized_username = str(username or "").strip()
        if not normalized_id:
            raise ValueError("user_id is required")
        if not normalized_username:
            raise ValueError("username is required")
        normalized_role = normalize_role(role)

        if self._phase_a_enabled and self._phase_a_store is not None:
            return self._phase_a_store.upsert_app_user(
                user_id=normalized_id,
                username=normalized_username,
                role=normalized_role,
                display_name=display_name,
                password_hash=password_hash,
                mfa_enabled=mfa_enabled,
                mfa_secret_ref=mfa_secret_ref,
                mfa_recovery_codes_hash=mfa_recovery_codes_hash,
                mfa_created_at=mfa_created_at,
                mfa_enabled_at=mfa_enabled_at,
                mfa_last_verified_at=mfa_last_verified_at,
                is_active=bool(is_active),
            )

        return self._sqlite_create_or_update_app_user(
            user_id=normalized_id,
            username=normalized_username,
            role=normalized_role,
            display_name=display_name,
            password_hash=password_hash,
            mfa_enabled=mfa_enabled,
            mfa_secret_ref=mfa_secret_ref,
            mfa_recovery_codes_hash=mfa_recovery_codes_hash,
            mfa_created_at=mfa_created_at,
            mfa_enabled_at=mfa_enabled_at,
            mfa_last_verified_at=mfa_last_verified_at,
            is_active=bool(is_active),
        )

    def update_app_user_mfa(
        self,
        *,
        user_id: str,
        mfa_enabled: bool,
        mfa_secret_ref: Optional[str] = None,
        mfa_recovery_codes_hash: Optional[str] = None,
        mfa_created_at: Optional[datetime] = None,
        mfa_enabled_at: Optional[datetime] = None,
        mfa_last_verified_at: Optional[datetime] = None,
    ) -> Optional[AppUser]:
        normalized_id = str(user_id or "").strip()
        if not normalized_id:
            return None
        if self._phase_a_enabled and self._phase_a_store is not None:
            row = self._phase_a_store.get_app_user(normalized_id)
            if row is None:
                return None
            return self._phase_a_store.upsert_app_user(
                user_id=str(row.id),
                username=str(row.username),
                role=str(row.role),
                display_name=getattr(row, "display_name", None),
                password_hash=getattr(row, "password_hash", None),
                mfa_enabled=mfa_enabled,
                mfa_secret_ref=mfa_secret_ref,
                mfa_recovery_codes_hash=mfa_recovery_codes_hash,
                mfa_created_at=mfa_created_at,
                mfa_enabled_at=mfa_enabled_at,
                mfa_last_verified_at=mfa_last_verified_at,
                is_active=bool(getattr(row, "is_active", True)),
                created_at=getattr(row, "created_at", None),
                updated_at=datetime.now(),
            )
        return self._sqlite_update_app_user_mfa(
            user_id=normalized_id,
            mfa_enabled=mfa_enabled,
            mfa_secret_ref=mfa_secret_ref,
            mfa_recovery_codes_hash=mfa_recovery_codes_hash,
            mfa_created_at=mfa_created_at,
            mfa_enabled_at=mfa_enabled_at,
            mfa_last_verified_at=mfa_last_verified_at,
        )

    def create_app_user_session(
        self,
        *,
        session_id: str,
        user_id: str,
        expires_at: datetime,
    ) -> AppUserSession:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            raise ValueError("session_id is required")
        resolved_user_id = self.require_user_id(user_id)
        if not isinstance(expires_at, datetime):
            raise ValueError("expires_at must be a datetime")

        if self._phase_a_enabled and self._phase_a_store is not None:
            return self._phase_a_store.upsert_app_user_session(
                session_id=normalized_session_id,
                user_id=resolved_user_id,
                expires_at=expires_at,
                revoked_at=None,
            )

        return self._sqlite_create_or_update_app_user_session(
            session_id=normalized_session_id,
            user_id=resolved_user_id,
            expires_at=expires_at,
            revoked_at=None,
        )

    def get_app_user_session(self, session_id: str) -> Optional[AppUserSession]:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return None
        if self._phase_a_enabled and self._phase_a_store is not None:
            row = self._phase_a_store.get_app_user_session(normalized_session_id)
            if row is not None:
                return row
            legacy_row = self._sqlite_get_app_user_session(normalized_session_id)
            if legacy_row is None:
                return None
            return self._sync_phase_a_session_from_legacy(legacy_row)
        return self._sqlite_get_app_user_session(normalized_session_id)

    def touch_app_user_session(self, session_id: str) -> bool:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return False
        if self._phase_a_enabled and self._phase_a_store is not None:
            if self._phase_a_store.touch_app_user_session(normalized_session_id):
                return True
            legacy_row = self._sqlite_get_app_user_session(normalized_session_id)
            if legacy_row is None:
                return False
            synced = self._sync_phase_a_session_from_legacy(legacy_row)
            if synced is None:
                return False
            return self._phase_a_store.touch_app_user_session(normalized_session_id)
        return self._sqlite_touch_app_user_session(normalized_session_id)

    def revoke_app_user_session(self, session_id: str) -> bool:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return False
        if self._phase_a_enabled and self._phase_a_store is not None:
            phase_a_revoked = self._phase_a_store.revoke_app_user_session(normalized_session_id)
            legacy_revoked = self._sqlite_revoke_app_user_session(normalized_session_id)
            if phase_a_revoked:
                return True
            legacy_row = self._sqlite_get_app_user_session(normalized_session_id)
            if legacy_row is not None:
                self._sync_phase_a_session_from_legacy(legacy_row)
                return self._phase_a_store.revoke_app_user_session(normalized_session_id) or legacy_revoked
            return legacy_revoked
        return self._sqlite_revoke_app_user_session(normalized_session_id)

    def revoke_all_app_user_sessions(self, user_id: str) -> int:
        resolved_user_id = self.require_user_id(user_id)
        if self._phase_a_enabled and self._phase_a_store is not None:
            active_session_ids = set(self._sqlite_list_active_app_user_session_ids(resolved_user_id))
            list_phase_a_active_ids = getattr(self._phase_a_store, "list_active_app_user_session_ids", None)
            if callable(list_phase_a_active_ids):
                active_session_ids.update(
                    str(value)
                    for value in list_phase_a_active_ids(resolved_user_id)
                    if str(value or "").strip()
                )
            phase_a_count = self._phase_a_store.revoke_all_app_user_sessions(resolved_user_id)
            legacy_count = self._sqlite_revoke_all_app_user_sessions(resolved_user_id)
            if active_session_ids:
                return len(active_session_ids)
            return max(phase_a_count, legacy_count)
        return self._sqlite_revoke_all_app_user_sessions(resolved_user_id)

    def get_auth_rate_limit_bucket(self, bucket_key: str) -> Optional[AuthRateLimitBucket]:
        normalized = str(bucket_key or "").strip()
        if not normalized:
            return None
        now = datetime.now()
        with self.session_scope() as session:
            session.execute(delete(AuthRateLimitBucket).where(AuthRateLimitBucket.expires_at <= now))
            row = session.execute(
                select(AuthRateLimitBucket).where(AuthRateLimitBucket.bucket_key == normalized).limit(1)
            ).scalar_one_or_none()
            if row is None:
                return None
            return SimpleNamespace(
                bucket_key=row.bucket_key,
                bucket_type=row.bucket_type,
                failure_count=row.failure_count,
                first_failed_at=row.first_failed_at,
                last_failed_at=row.last_failed_at,
                expires_at=row.expires_at,
            )

    def record_auth_rate_limit_failure(
        self,
        *,
        bucket_key: str,
        bucket_type: str,
        window_seconds: int,
    ) -> int:
        normalized_key = str(bucket_key or "").strip()
        normalized_type = str(bucket_type or "").strip()[:16] or "unknown"
        if not normalized_key:
            return 0
        now = datetime.now()
        window = max(60, int(window_seconds or 300))
        expires_at = now + timedelta(seconds=window)
        with self.session_scope() as session:
            session.execute(delete(AuthRateLimitBucket).where(AuthRateLimitBucket.expires_at <= now))
            row = session.execute(
                select(AuthRateLimitBucket).where(AuthRateLimitBucket.bucket_key == normalized_key).limit(1)
            ).scalar_one_or_none()
            if row is None:
                row = AuthRateLimitBucket(
                    bucket_key=normalized_key,
                    bucket_type=normalized_type,
                    failure_count=1,
                    first_failed_at=now,
                    last_failed_at=now,
                    expires_at=expires_at,
                )
                session.add(row)
                return 1
            if row.expires_at <= now:
                row.failure_count = 1
                row.first_failed_at = now
            else:
                row.failure_count = int(row.failure_count or 0) + 1
            row.bucket_type = normalized_type
            row.last_failed_at = now
            row.expires_at = expires_at
            return int(row.failure_count or 0)

    def clear_auth_rate_limit_buckets(self, bucket_keys: Iterable[str]) -> None:
        normalized_keys = [str(value or "").strip() for value in bucket_keys if str(value or "").strip()]
        if not normalized_keys:
            return
        with self.session_scope() as session:
            session.execute(delete(AuthRateLimitBucket).where(AuthRateLimitBucket.bucket_key.in_(normalized_keys)))

    def factory_reset_non_bootstrap_state(self) -> Dict[str, Any]:
        """Clear bounded non-bootstrap user-owned state while preserving system bootstrap rows."""
        user_ids = self._collect_known_user_ids()
        if not user_ids:
            return {
                "cleared": [],
                "counts": {},
            }

        with self.session_scope() as session:
            counts: Dict[str, int] = {}

            session_ids = session.execute(
                select(ConversationSessionRecord.session_id)
                .where(ConversationSessionRecord.owner_id.in_(user_ids))
            ).scalars().all()
            if session_ids:
                counts["conversation_messages"] = session.execute(
                    delete(ConversationMessage).where(ConversationMessage.session_id.in_(session_ids))
                ).rowcount or 0
            else:
                counts["conversation_messages"] = 0
            counts["conversation_sessions"] = session.execute(
                delete(ConversationSessionRecord).where(ConversationSessionRecord.owner_id.in_(user_ids))
            ).rowcount or 0

            analysis_ids = session.execute(
                select(AnalysisHistory.id).where(AnalysisHistory.owner_id.in_(user_ids))
            ).scalars().all()
            if analysis_ids:
                counts["backtest_results"] = session.execute(
                    delete(BacktestResult).where(BacktestResult.analysis_history_id.in_(analysis_ids))
                ).rowcount or 0
            else:
                counts["backtest_results"] = 0
            counts["analysis_history"] = session.execute(
                delete(AnalysisHistory).where(AnalysisHistory.owner_id.in_(user_ids))
            ).rowcount or 0
            counts["backtest_summaries"] = session.execute(
                delete(BacktestSummary).where(BacktestSummary.owner_id.in_(user_ids))
            ).rowcount or 0
            counts["backtest_runs"] = session.execute(
                delete(BacktestRun).where(BacktestRun.owner_id.in_(user_ids))
            ).rowcount or 0

            rule_run_ids = session.execute(
                select(RuleBacktestRun.id).where(RuleBacktestRun.owner_id.in_(user_ids))
            ).scalars().all()
            if rule_run_ids:
                counts["rule_backtest_trades"] = session.execute(
                    delete(RuleBacktestTrade).where(RuleBacktestTrade.run_id.in_(rule_run_ids))
                ).rowcount or 0
            else:
                counts["rule_backtest_trades"] = 0
            counts["rule_backtest_runs"] = session.execute(
                delete(RuleBacktestRun).where(RuleBacktestRun.owner_id.in_(user_ids))
            ).rowcount or 0

            scanner_run_ids = session.execute(
                select(MarketScannerRun.id).where(MarketScannerRun.owner_id.in_(user_ids))
            ).scalars().all()
            if scanner_run_ids:
                counts["scanner_candidates"] = session.execute(
                    delete(MarketScannerCandidate).where(MarketScannerCandidate.run_id.in_(scanner_run_ids))
                ).rowcount or 0
            else:
                counts["scanner_candidates"] = 0
            counts["scanner_runs"] = session.execute(
                delete(MarketScannerRun).where(MarketScannerRun.owner_id.in_(user_ids))
            ).rowcount or 0

            account_ids = session.execute(
                select(PortfolioAccount.id).where(PortfolioAccount.owner_id.in_(user_ids))
            ).scalars().all()
            connection_ids = session.execute(
                select(PortfolioBrokerConnection.id).where(PortfolioBrokerConnection.owner_id.in_(user_ids))
            ).scalars().all()

            counts["portfolio_sync_positions"] = session.execute(
                delete(PortfolioBrokerSyncPosition).where(PortfolioBrokerSyncPosition.owner_id.in_(user_ids))
            ).rowcount or 0
            counts["portfolio_sync_cash_balances"] = session.execute(
                delete(PortfolioBrokerSyncCashBalance).where(PortfolioBrokerSyncCashBalance.owner_id.in_(user_ids))
            ).rowcount or 0
            counts["portfolio_sync_states"] = session.execute(
                delete(PortfolioBrokerSyncState).where(PortfolioBrokerSyncState.owner_id.in_(user_ids))
            ).rowcount or 0

            if account_ids:
                counts["portfolio_position_lots"] = session.execute(
                    delete(PortfolioPositionLot).where(PortfolioPositionLot.account_id.in_(account_ids))
                ).rowcount or 0
                counts["portfolio_positions"] = session.execute(
                    delete(PortfolioPosition).where(PortfolioPosition.account_id.in_(account_ids))
                ).rowcount or 0
                counts["portfolio_daily_snapshots"] = session.execute(
                    delete(PortfolioDailySnapshot).where(PortfolioDailySnapshot.account_id.in_(account_ids))
                ).rowcount or 0
                counts["portfolio_corporate_actions"] = session.execute(
                    delete(PortfolioCorporateAction).where(PortfolioCorporateAction.account_id.in_(account_ids))
                ).rowcount or 0
                counts["portfolio_cash_ledger"] = session.execute(
                    delete(PortfolioCashLedger).where(PortfolioCashLedger.account_id.in_(account_ids))
                ).rowcount or 0
                counts["portfolio_trades"] = session.execute(
                    delete(PortfolioTrade).where(PortfolioTrade.account_id.in_(account_ids))
                ).rowcount or 0
            else:
                counts["portfolio_position_lots"] = 0
                counts["portfolio_positions"] = 0
                counts["portfolio_daily_snapshots"] = 0
                counts["portfolio_corporate_actions"] = 0
                counts["portfolio_cash_ledger"] = 0
                counts["portfolio_trades"] = 0

            if connection_ids:
                counts["portfolio_broker_connections"] = session.execute(
                    delete(PortfolioBrokerConnection).where(PortfolioBrokerConnection.id.in_(connection_ids))
                ).rowcount or 0
            else:
                counts["portfolio_broker_connections"] = 0
            counts["user_watchlist_items"] = session.execute(
                delete(UserWatchlistItem).where(UserWatchlistItem.owner_id.in_(user_ids))
            ).rowcount or 0
            counts["user_alert_events"] = session.execute(
                delete(UserAlertEvent).where(UserAlertEvent.owner_id.in_(user_ids))
            ).rowcount or 0
            counts["user_alert_rules"] = session.execute(
                delete(UserAlertRule).where(UserAlertRule.owner_id.in_(user_ids))
            ).rowcount or 0
            counts["portfolio_accounts"] = session.execute(
                delete(PortfolioAccount).where(PortfolioAccount.owner_id.in_(user_ids))
            ).rowcount or 0

            counts["user_preferences"] = session.execute(
                delete(UserPreference).where(UserPreference.user_id.in_(user_ids))
            ).rowcount or 0
            counts["app_user_sessions"] = session.execute(
                delete(AppUserSession).where(AppUserSession.user_id.in_(user_ids))
            ).rowcount or 0
            counts["app_users"] = session.execute(
                delete(AppUser).where(AppUser.id.in_(user_ids))
            ).rowcount or 0

        if self._phase_b_enabled and self._phase_b_store is not None:
            phase_b_counts = self._phase_b_store.clear_non_bootstrap_state(user_ids)
            counts["conversation_messages"] = counts.get("conversation_messages", 0) + int(
                phase_b_counts.get("chat_messages", 0)
            )
            counts["conversation_sessions"] = counts.get("conversation_sessions", 0) + int(
                phase_b_counts.get("chat_sessions", 0)
            )
            counts["analysis_history"] = counts.get("analysis_history", 0) + int(
                phase_b_counts.get("analysis_records", 0)
            )
            counts["analysis_sessions"] = int(phase_b_counts.get("analysis_sessions", 0))
        if self._phase_d_enabled and self._phase_d_store is not None:
            phase_d_counts = self._phase_d_store.clear_non_bootstrap_state(user_ids)
            counts["scanner_candidates"] = counts.get("scanner_candidates", 0) + int(
                phase_d_counts.get("scanner_candidates", 0)
            )
            counts["scanner_runs"] = counts.get("scanner_runs", 0) + int(
                phase_d_counts.get("scanner_runs", 0)
            )
            counts["watchlist_items"] = int(phase_d_counts.get("watchlist_items", 0))
            counts["watchlists"] = int(phase_d_counts.get("watchlists", 0))
        if self._phase_e_enabled and self._phase_e_store is not None:
            phase_e_counts = self._phase_e_store.clear_non_bootstrap_state(user_ids)
            counts["backtest_runs"] = counts.get("backtest_runs", 0) + int(
                phase_e_counts.get("backtest_runs", 0)
            )
            counts["backtest_artifacts"] = int(phase_e_counts.get("backtest_artifacts", 0))
            counts["market_data_usage_refs"] = counts.get("market_data_usage_refs", 0) + int(
                phase_e_counts.get("market_data_usage_refs", 0)
            )
        if self._phase_f_enabled and self._phase_f_store is not None:
            phase_f_counts = self._phase_f_store.clear_non_bootstrap_state(user_ids)
            counts["portfolio_accounts"] = counts.get("portfolio_accounts", 0) + int(
                phase_f_counts.get("portfolio_accounts", 0)
            )
            counts["portfolio_broker_connections"] = counts.get("portfolio_broker_connections", 0) + int(
                phase_f_counts.get("broker_connections", 0)
            )
            counts["portfolio_positions"] = counts.get("portfolio_positions", 0) + int(
                phase_f_counts.get("portfolio_positions", 0)
            )
            counts["portfolio_sync_states"] = counts.get("portfolio_sync_states", 0) + int(
                phase_f_counts.get("portfolio_sync_states", 0)
            )
            counts["portfolio_sync_positions"] = counts.get("portfolio_sync_positions", 0) + int(
                phase_f_counts.get("portfolio_sync_positions", 0)
            )
            counts["portfolio_sync_cash_balances"] = counts.get("portfolio_sync_cash_balances", 0) + int(
                phase_f_counts.get("portfolio_sync_cash_balances", 0)
            )
            counts["portfolio_ledger"] = int(phase_f_counts.get("portfolio_ledger", 0))
        if self._phase_g_enabled and self._phase_g_store is not None:
            self._phase_g_store.nullify_user_references(user_ids)
        if self._phase_a_enabled and self._phase_a_store is not None:
            phase_a_counts = self._phase_a_store.clear_non_bootstrap_state(user_ids)
            counts["user_preferences"] = counts.get("user_preferences", 0) + int(
                phase_a_counts.get("user_preferences", 0)
            )
            counts["app_user_sessions"] = counts.get("app_user_sessions", 0) + int(
                phase_a_counts.get("app_user_sessions", 0)
            )
            counts["app_users"] = counts.get("app_users", 0) + int(
                phase_a_counts.get("app_users", 0)
            )
            counts["notification_targets"] = int(
                phase_a_counts.get("notification_targets", 0)
            )

        cleared = [key for key, value in counts.items() if int(value or 0) > 0]
        return {
            "cleared": cleared,
            "counts": counts,
        }

    def get_user_notification_preferences(self, user_id: str) -> Dict[str, Any]:
        resolved_user_id = self.require_user_id(user_id)
        if self._phase_a_enabled and self._phase_a_store is not None:
            preferences = self._phase_a_store.get_user_notification_preferences(resolved_user_id)
            if (
                preferences.get("updated_at") is not None
                or preferences.get("email") is not None
                or preferences.get("discord_webhook") is not None
            ):
                return preferences
            legacy_preferences = self._sync_phase_a_notification_preferences_from_legacy(resolved_user_id)
            if legacy_preferences is not None:
                return legacy_preferences
            return preferences

        row = self._sqlite_get_user_preference_row(resolved_user_id)
        payload = self._safe_json_loads(
            getattr(row, "notification_preferences_json", None),
            {},
        )
        if not isinstance(payload, dict):
            payload = {}

        email = str(payload.get("email") or "").strip() or None
        email_enabled = bool(payload.get("email_enabled", payload.get("enabled"))) and bool(email)
        discord_webhook = str(payload.get("discord_webhook") or "").strip() or None
        discord_enabled = bool(payload.get("discord_enabled")) and bool(discord_webhook)
        channel = str(payload.get("channel") or "email").strip().lower() or "email"
        if email_enabled and discord_enabled:
            channel = "multi"
        elif discord_enabled and not email_enabled:
            channel = "discord"
        else:
            channel = "email"
        updated_at = getattr(row, "updated_at", None)
        return {
            "channel": channel,
            "enabled": email_enabled,
            "email": email,
            "email_enabled": email_enabled,
            "discord_webhook": discord_webhook,
            "discord_enabled": discord_enabled,
            "updated_at": updated_at.isoformat() if updated_at else None,
        }

    def get_symbol_master_entry(self, canonical_symbol: str) -> Optional[Any]:
        if not self._phase_c_enabled or self._phase_c_store is None:
            return None
        return self._phase_c_store.get_symbol_master_entry(canonical_symbol)

    def upsert_symbol_master_entry(
        self,
        *,
        canonical_symbol: str,
        display_symbol: Optional[str] = None,
        market: str,
        asset_type: str,
        display_name: Optional[str] = None,
        exchange_code: Optional[str] = None,
        currency: Optional[str] = None,
        lot_size: Optional[Any] = None,
        is_active: bool = True,
        search_aliases: Optional[List[Any]] = None,
        source: Optional[str] = None,
        source_payload: Optional[Dict[str, Any]] = None,
    ) -> Optional[Any]:
        if not self._phase_c_enabled or self._phase_c_store is None:
            return None
        return self._phase_c_store.upsert_symbol_master_entry(
            canonical_symbol=canonical_symbol,
            display_symbol=display_symbol,
            market=market,
            asset_type=asset_type,
            display_name=display_name,
            exchange_code=exchange_code,
            currency=currency,
            lot_size=lot_size,
            is_active=is_active,
            search_aliases=search_aliases,
            source=source,
            source_payload=source_payload,
        )

    def seed_symbol_master_from_stock_mapping(self, *, symbols: Optional[List[str]] = None) -> int:
        if not self._phase_c_enabled or self._phase_c_store is None:
            return 0
        return self._phase_c_store.seed_symbol_master_from_stock_mapping(symbols=symbols)

    def get_market_data_manifest(self, manifest_key: str) -> Optional[Any]:
        if not self._phase_c_enabled or self._phase_c_store is None:
            return None
        return self._phase_c_store.get_market_data_manifest(manifest_key)

    def upsert_market_data_manifest(
        self,
        *,
        manifest_key: str,
        dataset_family: str,
        market: str,
        storage_backend: str,
        root_uri: str,
        asset_scope: Optional[str] = None,
        file_format: str = "parquet",
        partition_strategy: Optional[str] = None,
        symbol_namespace: Optional[str] = None,
        description: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        active_version_id: Optional[int] = None,
    ) -> Optional[Any]:
        if not self._phase_c_enabled or self._phase_c_store is None:
            return None
        return self._phase_c_store.upsert_market_data_manifest(
            manifest_key=manifest_key,
            dataset_family=dataset_family,
            market=market,
            storage_backend=storage_backend,
            root_uri=root_uri,
            asset_scope=asset_scope,
            file_format=file_format,
            partition_strategy=partition_strategy,
            symbol_namespace=symbol_namespace,
            description=description,
            config=config,
            active_version_id=active_version_id,
        )

    def get_market_dataset_version(self, dataset_version_id: int) -> Optional[Any]:
        if not self._phase_c_enabled or self._phase_c_store is None:
            return None
        return self._phase_c_store.get_market_dataset_version(dataset_version_id)

    def register_market_dataset_version(
        self,
        *,
        manifest_key: str,
        version_label: str,
        version_hash: str,
        source_kind: Optional[str] = None,
        generated_at: Optional[datetime] = None,
        as_of_date: Optional[date] = None,
        coverage_start: Optional[date] = None,
        coverage_end: Optional[date] = None,
        symbol_count: Optional[int] = None,
        row_count: Optional[int] = None,
        partition_count: Optional[int] = None,
        file_inventory: Optional[Dict[str, Any]] = None,
        content_stats: Optional[Dict[str, Any]] = None,
        set_active: bool = False,
    ) -> Optional[Any]:
        if not self._phase_c_enabled or self._phase_c_store is None:
            return None
        return self._phase_c_store.register_market_dataset_version(
            manifest_key=manifest_key,
            version_label=version_label,
            version_hash=version_hash,
            source_kind=source_kind,
            generated_at=generated_at,
            as_of_date=as_of_date,
            coverage_start=coverage_start,
            coverage_end=coverage_end,
            symbol_count=symbol_count,
            row_count=row_count,
            partition_count=partition_count,
            file_inventory=file_inventory,
            content_stats=content_stats,
            set_active=set_active,
        )

    def get_market_data_usage_refs(
        self,
        *,
        entity_type: str,
        entity_id: int,
    ) -> List[Any]:
        if not self._phase_c_enabled or self._phase_c_store is None:
            return []
        return self._phase_c_store.get_market_data_usage_refs(
            entity_type=entity_type,
            entity_id=entity_id,
        )

    def record_market_data_usage_ref(
        self,
        *,
        entity_type: str,
        entity_id: int,
        usage_role: str,
        manifest_key: str,
        dataset_version_id: int,
        detail: Optional[Dict[str, Any]] = None,
    ) -> Optional[Any]:
        if not self._phase_c_enabled or self._phase_c_store is None:
            return None
        return self._phase_c_store.record_market_data_usage_ref(
            entity_type=entity_type,
            entity_id=entity_id,
            usage_role=usage_role,
            manifest_key=manifest_key,
            dataset_version_id=dataset_version_id,
            detail=detail,
        )

    def register_local_us_parquet_dataset_version(
        self,
        *,
        root_path: Optional[Any] = None,
        activate: bool = True,
    ) -> Optional[Any]:
        if not self._phase_c_enabled or self._phase_c_store is None:
            return None
        return self._phase_c_store.register_local_us_parquet_dataset_version(
            root_path=root_path,
            activate=activate,
        )

    def build_local_us_parquet_usage_detail(
        self,
        *,
        stock_code: str,
        file_path: Any,
        dataframe: Optional[Any],
        source_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self._phase_c_enabled or self._phase_c_store is None:
            return {}
        return self._phase_c_store.build_local_us_parquet_usage_detail(
            stock_code=stock_code,
            file_path=file_path,
            dataframe=dataframe,
            source_name=source_name,
        )

    def sync_phase_e_analysis_backtest_shadow(self, run_id: int) -> Optional[Any]:
        if not self._phase_e_enabled or self._phase_e_store is None:
            return None

        with self.get_session() as session:
            run_row = session.execute(
                select(BacktestRun).where(BacktestRun.id == int(run_id)).limit(1)
            ).scalar_one_or_none()
            if run_row is None:
                return None

            evaluated_at = getattr(run_row, "completed_at", None) or getattr(run_row, "run_at", None)
            result_rows = session.execute(
                select(BacktestResult)
                .where(
                    and_(
                        BacktestResult.owner_id == run_row.owner_id,
                        BacktestResult.evaluated_at == evaluated_at,
                    )
                )
                .order_by(BacktestResult.analysis_history_id.asc(), BacktestResult.id.asc())
            ).scalars().all() if evaluated_at is not None else []

            summary_rows: List[BacktestSummary] = []
            engine_versions = sorted({str(getattr(row, "engine_version", "") or "").strip() for row in result_rows if str(getattr(row, "engine_version", "") or "").strip()})
            if engine_versions:
                engine_version = engine_versions[0]
                summary_conditions = [
                    BacktestSummary.owner_id == run_row.owner_id,
                    BacktestSummary.eval_window_days == run_row.eval_window_days,
                    BacktestSummary.engine_version == engine_version,
                ]
                code_values = [run_row.code] if str(getattr(run_row, "code", "") or "").strip() else []
                code_values.append("__overall__")
                summary_rows = session.execute(
                    select(BacktestSummary)
                    .where(and_(*summary_conditions))
                    .where(BacktestSummary.code.in_(code_values))
                    .order_by(BacktestSummary.scope.asc(), BacktestSummary.code.asc())
                ).scalars().all()

        shadow_row = self._phase_e_store.upsert_analysis_eval_run_shadow(
            run_row=run_row,
            result_rows=result_rows,
            summary_rows=summary_rows,
        )
        self._record_phase_e_analysis_usage_ref(run_row=run_row, shadow_row=shadow_row)
        return shadow_row

    def _record_phase_e_analysis_usage_ref(self, *, run_row: BacktestRun, shadow_row: Optional[Any]) -> None:
        if shadow_row is None:
            return
        if not self._phase_c_enabled or self._phase_c_store is None:
            return

        summary = self._safe_json_loads(getattr(run_row, "summary_json", None), {})
        resolved_source = str(summary.get("resolved_source") or "").strip()
        if resolved_source != "LocalParquet":
            return

        canonical_symbol = str(getattr(run_row, "code", "") or "").strip().upper()
        if not canonical_symbol:
            return

        try:
            version = self.register_local_us_parquet_dataset_version()
            if version is None:
                return
            self.record_market_data_usage_ref(
                entity_type="backtest_run",
                entity_id=int(shadow_row.id),
                usage_role="primary_bars",
                manifest_key="us.local_parquet.daily",
                dataset_version_id=int(version.id),
                detail={
                    "symbol": canonical_symbol,
                    "resolved_source": LOCAL_US_PARQUET_SOURCE,
                    "provenance_granularity": "manifest_version",
                },
            )
        except Exception as exc:
            logger.warning("Failed to record Phase E market-data usage ref for run %s: %s", run_row.id, exc)

    def delete_phase_e_analysis_backtest_shadow_by_code(
        self,
        *,
        code: str,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> int:
        if not self._phase_e_enabled or self._phase_e_store is None:
            return 0
        resolved_owner_id = None if include_all_owners else self.require_user_id(owner_id)
        return self._phase_e_store.delete_backtest_shadows_by_code(
            run_type="analysis_eval",
            code=code,
            owner_user_id=resolved_owner_id,
            include_all_owners=include_all_owners,
        )

    def sync_phase_e_rule_backtest_shadow(self, run_id: int) -> Optional[Any]:
        if not self._phase_e_enabled or self._phase_e_store is None:
            return None

        with self.get_session() as session:
            run_row = session.execute(
                select(RuleBacktestRun).where(RuleBacktestRun.id == int(run_id)).limit(1)
            ).scalar_one_or_none()
            if run_row is None:
                return None
            trade_rows = session.execute(
                select(RuleBacktestTrade)
                .where(RuleBacktestTrade.run_id == int(run_id))
                .order_by(RuleBacktestTrade.trade_index.asc(), RuleBacktestTrade.id.asc())
            ).scalars().all()

        return self._phase_e_store.upsert_rule_backtest_run_shadow(
            run_row=run_row,
            trade_rows=trade_rows,
        )

    def delete_phase_e_rule_backtest_shadow_by_code(
        self,
        *,
        code: str,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> int:
        if not self._phase_e_enabled or self._phase_e_store is None:
            return 0
        resolved_owner_id = None if include_all_owners else self.require_user_id(owner_id)
        return self._phase_e_store.delete_backtest_shadows_by_code(
            run_type="rule_deterministic",
            code=code,
            owner_user_id=resolved_owner_id,
            include_all_owners=include_all_owners,
        )

    def _load_phase_f_portfolio_projection_in_session(
        self,
        *,
        session: Session,
        account_id: int,
    ) -> Optional[Dict[str, Any]]:
        resolved_account_id = int(account_id)
        account_row = session.execute(
            select(PortfolioAccount).where(PortfolioAccount.id == resolved_account_id).limit(1)
        ).scalar_one_or_none()
        if account_row is None:
            return None

        return {
            "account_row": account_row,
            "broker_connection_rows": session.execute(
                select(PortfolioBrokerConnection)
                .where(PortfolioBrokerConnection.portfolio_account_id == resolved_account_id)
                .order_by(PortfolioBrokerConnection.id.asc())
            ).scalars().all(),
            "trade_rows": session.execute(
                select(PortfolioTrade)
                .where(
                    and_(
                        PortfolioTrade.account_id == resolved_account_id,
                        or_(PortfolioTrade.is_active.is_(True), PortfolioTrade.is_active.is_(None)),
                    )
                )
                .order_by(PortfolioTrade.trade_date.asc(), PortfolioTrade.id.asc())
            ).scalars().all(),
            "cash_rows": session.execute(
                select(PortfolioCashLedger)
                .where(PortfolioCashLedger.account_id == resolved_account_id)
                .order_by(PortfolioCashLedger.event_date.asc(), PortfolioCashLedger.id.asc())
            ).scalars().all(),
            "corporate_action_rows": session.execute(
                select(PortfolioCorporateAction)
                .where(PortfolioCorporateAction.account_id == resolved_account_id)
                .order_by(PortfolioCorporateAction.effective_date.asc(), PortfolioCorporateAction.id.asc())
            ).scalars().all(),
            "position_rows": session.execute(
                select(PortfolioPosition)
                .where(PortfolioPosition.account_id == resolved_account_id)
                .order_by(
                    PortfolioPosition.cost_method.asc(),
                    PortfolioPosition.symbol.asc(),
                    PortfolioPosition.market.asc(),
                    PortfolioPosition.currency.asc(),
                    PortfolioPosition.id.asc(),
                )
            ).scalars().all(),
            "snapshot_rows": session.execute(
                select(PortfolioDailySnapshot)
                .where(PortfolioDailySnapshot.account_id == resolved_account_id)
                .order_by(
                    PortfolioDailySnapshot.cost_method.asc(),
                    PortfolioDailySnapshot.snapshot_date.desc(),
                    PortfolioDailySnapshot.id.desc(),
                )
            ).scalars().all(),
            "sync_state_rows": session.execute(
                select(PortfolioBrokerSyncState)
                .where(PortfolioBrokerSyncState.portfolio_account_id == resolved_account_id)
                .order_by(PortfolioBrokerSyncState.broker_connection_id.asc(), PortfolioBrokerSyncState.id.asc())
            ).scalars().all(),
            "sync_position_rows": session.execute(
                select(PortfolioBrokerSyncPosition)
                .where(PortfolioBrokerSyncPosition.portfolio_account_id == resolved_account_id)
                .order_by(
                    PortfolioBrokerSyncPosition.broker_connection_id.asc(),
                    PortfolioBrokerSyncPosition.symbol.asc(),
                    PortfolioBrokerSyncPosition.market.asc(),
                    PortfolioBrokerSyncPosition.currency.asc(),
                    PortfolioBrokerSyncPosition.id.asc(),
                )
            ).scalars().all(),
            "sync_cash_balance_rows": session.execute(
                select(PortfolioBrokerSyncCashBalance)
                .where(PortfolioBrokerSyncCashBalance.portfolio_account_id == resolved_account_id)
                .order_by(
                    PortfolioBrokerSyncCashBalance.broker_connection_id.asc(),
                    PortfolioBrokerSyncCashBalance.currency.asc(),
                    PortfolioBrokerSyncCashBalance.id.asc(),
                )
            ).scalars().all(),
        }

    def sync_phase_f_portfolio_account_shadow_from_session(
        self,
        *,
        session: Session,
        account_id: int,
    ) -> bool:
        if not self._phase_f_enabled or self._phase_f_store is None:
            return False

        resolved_account_id = int(account_id)
        session.flush()
        projection = self._load_phase_f_portfolio_projection_in_session(
            session=session,
            account_id=resolved_account_id,
        )
        if projection is None:
            self._phase_f_store.delete_account_shadow(account_id=resolved_account_id)
            return False

        if not list(projection.get("position_rows") or []):
            shadow_bundle = self._phase_f_store.get_account_shadow_bundle(account_id=resolved_account_id)
            preserved_shadow_positions = list((shadow_bundle or {}).get("positions") or [])
            if preserved_shadow_positions:
                hydrated_position_rows: List[Any] = []
                for row in preserved_shadow_positions:
                    updated_at_raw = row.get("updated_at")
                    updated_at = None
                    if updated_at_raw:
                        try:
                            updated_at = datetime.fromisoformat(str(updated_at_raw))
                        except ValueError:
                            updated_at = None
                    hydrated_position_rows.append(
                        SimpleNamespace(
                            id=int(row.get("id") or 0),
                            cost_method=str(row.get("cost_method", "") or "fifo"),
                            symbol=str(row.get("canonical_symbol", "") or ""),
                            market=str(row.get("market", "") or ""),
                            currency=str(row.get("currency", "") or ""),
                            quantity=float(row.get("quantity", 0.0) or 0.0),
                            avg_cost=float(row.get("avg_cost", 0.0) or 0.0),
                            total_cost=float(row.get("total_cost", 0.0) or 0.0),
                            last_price=(
                                float(row.get("last_price"))
                                if row.get("last_price") is not None
                                else None
                            ),
                            market_value_base=(
                                float(row.get("market_value_base"))
                                if row.get("market_value_base") is not None
                                else None
                            ),
                            unrealized_pnl_base=(
                                float(row.get("unrealized_pnl_base"))
                                if row.get("unrealized_pnl_base") is not None
                                else None
                            ),
                            valuation_currency=row.get("valuation_currency"),
                            updated_at=updated_at,
                        )
                    )
                projection["position_rows"] = hydrated_position_rows

        self._phase_f_store.replace_account_shadow(**projection)
        return True

    def sync_phase_f_portfolio_account_shadow(self, account_id: int) -> bool:
        if not self._phase_f_enabled or self._phase_f_store is None:
            return False
        with self.get_session() as session:
            return self.sync_phase_f_portfolio_account_shadow_from_session(
                session=session,
                account_id=account_id,
            )

    def sync_phase_f_portfolio_account_shadows(self, account_ids: Iterable[int]) -> int:
        if not self._phase_f_enabled or self._phase_f_store is None:
            return 0
        synced = 0
        with self.get_session() as session:
            for account_id in sorted({int(item) for item in account_ids if item is not None}):
                if self.sync_phase_f_portfolio_account_shadow_from_session(
                    session=session,
                    account_id=account_id,
                ):
                    synced += 1
        return synced

    @staticmethod
    def _phase_f_account_metadata_row(row: Any) -> Any:
        return SimpleNamespace(
            id=int(row.id),
            owner_id=str(getattr(row, "owner_user_id", "") or ""),
            name=str(getattr(row, "name", "") or ""),
            broker=getattr(row, "broker_label", None),
            market=str(getattr(row, "market", "") or ""),
            base_currency=str(getattr(row, "base_currency", "") or ""),
            is_active=bool(getattr(row, "is_active", True)),
            created_at=getattr(row, "created_at", None),
            updated_at=getattr(row, "updated_at", None),
        )

    @staticmethod
    def _phase_f_json_payload(value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return dict(value)
        if isinstance(value, str):
            raw_text = value.strip()
            if not raw_text:
                return {}
            try:
                parsed = json.loads(raw_text)
            except Exception:
                return {}
            if isinstance(parsed, dict):
                return parsed
        return {}

    @staticmethod
    def _phase_f_json_text(value: Any) -> str:
        return json.dumps(
            DatabaseManager._phase_f_json_payload(value),
            ensure_ascii=False,
            sort_keys=True,
        )

    @staticmethod
    def _phase_f_normalize_compare_time_value(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, date):
            return value.isoformat()
        elif isinstance(value, str):
            raw_value = value.strip()
            if not raw_value:
                return None
            if "T" not in raw_value and " " not in raw_value:
                try:
                    return date.fromisoformat(raw_value).isoformat()
                except ValueError:
                    pass
            try:
                parsed = datetime.fromisoformat(raw_value)
            except ValueError:
                return value
        else:
            return value

        if parsed.tzinfo is not None:
            parsed = parsed.replace(tzinfo=None)
        return parsed.isoformat()

    @classmethod
    def _phase_f_normalize_compare_time_fields(
        cls,
        payload: Dict[str, Any],
        *,
        fields: Tuple[str, ...],
    ) -> Dict[str, Any]:
        normalized = dict(payload)
        for field in fields:
            normalized[field] = cls._phase_f_normalize_compare_time_value(normalized.get(field))
        return normalized

    @classmethod
    def _phase_f_shadow_account_payload(cls, row: Any) -> Dict[str, Any]:
        return cls._phase_f_normalize_compare_time_fields({
            "id": int(row.id),
            "owner_user_id": str(getattr(row, "owner_id", "") or ""),
            "name": str(getattr(row, "name", "") or ""),
            "broker_label": getattr(row, "broker", None),
            "market": str(getattr(row, "market", "") or ""),
            "base_currency": str(getattr(row, "base_currency", "") or ""),
            "is_active": bool(getattr(row, "is_active", True)),
            "created_at": getattr(row, "created_at", None),
            "updated_at": getattr(row, "updated_at", None),
        }, fields=("created_at", "updated_at"))

    @classmethod
    def _phase_f_shadow_broker_connection_payload(cls, row: Any) -> Dict[str, Any]:
        return cls._phase_f_normalize_compare_time_fields({
            "id": int(row.id),
            "owner_user_id": str(getattr(row, "owner_id", "") or ""),
            "portfolio_account_id": int(row.portfolio_account_id),
            "broker_type": str(getattr(row, "broker_type", "") or ""),
            "broker_name": getattr(row, "broker_name", None),
            "connection_name": str(getattr(row, "connection_name", "") or ""),
            "broker_account_ref": getattr(row, "broker_account_ref", None),
            "import_mode": str(getattr(row, "import_mode", "") or ""),
            "status": str(getattr(row, "status", "") or ""),
            "last_imported_at": getattr(row, "last_imported_at", None),
            "last_import_source": getattr(row, "last_import_source", None),
            "last_import_fingerprint": getattr(row, "last_import_fingerprint", None),
            "sync_metadata": DatabaseManager._phase_f_json_payload(getattr(row, "sync_metadata_json", None)),
            "created_at": getattr(row, "created_at", None),
            "updated_at": getattr(row, "updated_at", None),
        }, fields=("last_imported_at", "created_at", "updated_at"))

    @classmethod
    def _phase_f_shadow_sync_state_payload(cls, row: Any) -> Dict[str, Any]:
        return cls._phase_f_normalize_compare_time_fields({
            "id": int(row.id),
            "owner_user_id": str(getattr(row, "owner_id", "") or ""),
            "broker_connection_id": int(row.broker_connection_id),
            "portfolio_account_id": int(row.portfolio_account_id),
            "broker_type": str(getattr(row, "broker_type", "") or ""),
            "broker_account_ref": getattr(row, "broker_account_ref", None),
            "sync_source": str(getattr(row, "sync_source", "") or ""),
            "sync_status": str(getattr(row, "sync_status", "") or ""),
            "snapshot_date": getattr(row, "snapshot_date", None),
            "synced_at": getattr(row, "synced_at", None),
            "base_currency": str(getattr(row, "base_currency", "") or ""),
            "total_cash": float(getattr(row, "total_cash", 0.0) or 0.0),
            "total_market_value": float(getattr(row, "total_market_value", 0.0) or 0.0),
            "total_equity": float(getattr(row, "total_equity", 0.0) or 0.0),
            "realized_pnl": float(getattr(row, "realized_pnl", 0.0) or 0.0),
            "unrealized_pnl": float(getattr(row, "unrealized_pnl", 0.0) or 0.0),
            "fx_stale": bool(getattr(row, "fx_stale", False)),
            "payload_json": DatabaseManager._phase_f_json_payload(getattr(row, "payload_json", None)),
            "created_at": getattr(row, "created_at", None),
            "updated_at": getattr(row, "updated_at", None),
        }, fields=("snapshot_date", "synced_at", "created_at", "updated_at"))

    @classmethod
    def _phase_f_shadow_sync_position_payload(cls, row: Any) -> Dict[str, Any]:
        return cls._phase_f_normalize_compare_time_fields({
            "id": int(row.id),
            "portfolio_sync_state_id": int(getattr(row, "broker_connection_id", 0) or 0),
            "owner_user_id": str(getattr(row, "owner_id", "") or ""),
            "portfolio_account_id": int(row.portfolio_account_id),
            "broker_position_ref": getattr(row, "broker_position_ref", None),
            "canonical_symbol": str(getattr(row, "symbol", "") or ""),
            "market": str(getattr(row, "market", "") or ""),
            "currency": str(getattr(row, "currency", "") or ""),
            "quantity": float(getattr(row, "quantity", 0.0) or 0.0),
            "avg_cost": float(getattr(row, "avg_cost", 0.0) or 0.0),
            "last_price": float(getattr(row, "last_price", 0.0) or 0.0),
            "market_value_base": float(getattr(row, "market_value_base", 0.0) or 0.0),
            "unrealized_pnl_base": float(getattr(row, "unrealized_pnl_base", 0.0) or 0.0),
            "valuation_currency": getattr(row, "valuation_currency", None),
            "payload_json": DatabaseManager._phase_f_json_payload(getattr(row, "payload_json", None)),
            "created_at": getattr(row, "created_at", None),
            "updated_at": getattr(row, "updated_at", None),
        }, fields=("created_at", "updated_at"))

    @classmethod
    def _phase_f_shadow_sync_cash_balance_payload(cls, row: Any) -> Dict[str, Any]:
        return cls._phase_f_normalize_compare_time_fields({
            "id": int(row.id),
            "portfolio_sync_state_id": int(getattr(row, "broker_connection_id", 0) or 0),
            "owner_user_id": str(getattr(row, "owner_id", "") or ""),
            "portfolio_account_id": int(row.portfolio_account_id),
            "currency": str(getattr(row, "currency", "") or ""),
            "amount": float(getattr(row, "amount", 0.0) or 0.0),
            "amount_base": float(getattr(row, "amount_base", 0.0) or 0.0),
            "created_at": getattr(row, "created_at", None),
            "updated_at": getattr(row, "updated_at", None),
        }, fields=("created_at", "updated_at"))

    @staticmethod
    def _phase_f_broker_connection_metadata_row(
        row: Any,
        *,
        portfolio_account_name: Optional[str],
    ) -> Any:
        return SimpleNamespace(
            id=int(row.id),
            owner_id=str(getattr(row, "owner_user_id", "") or ""),
            portfolio_account_id=int(row.portfolio_account_id),
            portfolio_account_name=portfolio_account_name,
            broker_type=str(getattr(row, "broker_type", "") or ""),
            broker_name=getattr(row, "broker_name", None),
            connection_name=str(getattr(row, "connection_name", "") or ""),
            broker_account_ref=getattr(row, "broker_account_ref", None),
            import_mode=str(getattr(row, "import_mode", "") or ""),
            status=str(getattr(row, "status", "") or ""),
            last_imported_at=getattr(row, "last_imported_at", None),
            last_import_source=getattr(row, "last_import_source", None),
            last_import_fingerprint=getattr(row, "last_import_fingerprint", None),
            sync_metadata_json=DatabaseManager._phase_f_json_text(getattr(row, "sync_metadata", None)),
            created_at=getattr(row, "created_at", None),
            updated_at=getattr(row, "updated_at", None),
        )

    @staticmethod
    def _phase_f_broker_sync_state_row(row: Dict[str, Any]) -> Any:
        return SimpleNamespace(
            id=int(row["id"]),
            owner_id=str(row.get("owner_user_id", "") or ""),
            broker_connection_id=int(row["broker_connection_id"]),
            portfolio_account_id=int(row["portfolio_account_id"]),
            broker_type=str(row.get("broker_type", "") or ""),
            broker_account_ref=row.get("broker_account_ref"),
            sync_source=str(row.get("sync_source", "") or ""),
            sync_status=str(row.get("sync_status", "") or ""),
            snapshot_date=date.fromisoformat(row["snapshot_date"]) if row.get("snapshot_date") else None,
            synced_at=datetime.fromisoformat(row["synced_at"]) if row.get("synced_at") else None,
            base_currency=str(row.get("base_currency", "") or ""),
            total_cash=float(row.get("total_cash", 0.0) or 0.0),
            total_market_value=float(row.get("total_market_value", 0.0) or 0.0),
            total_equity=float(row.get("total_equity", 0.0) or 0.0),
            realized_pnl=float(row.get("realized_pnl", 0.0) or 0.0),
            unrealized_pnl=float(row.get("unrealized_pnl", 0.0) or 0.0),
            fx_stale=bool(row.get("fx_stale", False)),
            payload_json=DatabaseManager._phase_f_json_text(row.get("payload_json")),
            created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
            updated_at=datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else None,
        )

    @staticmethod
    def _phase_f_broker_sync_position_row(row: Dict[str, Any]) -> Any:
        return SimpleNamespace(
            id=int(row["id"]),
            broker_position_ref=row.get("broker_position_ref"),
            symbol=str(row.get("canonical_symbol", "") or ""),
            market=str(row.get("market", "") or ""),
            currency=str(row.get("currency", "") or ""),
            quantity=float(row.get("quantity", 0.0) or 0.0),
            avg_cost=float(row.get("avg_cost", 0.0) or 0.0),
            last_price=float(row.get("last_price", 0.0) or 0.0),
            market_value_base=float(row.get("market_value_base", 0.0) or 0.0),
            unrealized_pnl_base=float(row.get("unrealized_pnl_base", 0.0) or 0.0),
            valuation_currency=row.get("valuation_currency"),
        )

    @staticmethod
    def _phase_f_broker_sync_cash_balance_row(row: Dict[str, Any]) -> Any:
        return SimpleNamespace(
            id=int(row["id"]),
            currency=str(row.get("currency", "") or ""),
            amount=float(row.get("amount", 0.0) or 0.0),
            amount_base=float(row.get("amount_base", 0.0) or 0.0),
        )

    def _build_phase_f_portfolio_shadow_authority_state(
        self,
        *,
        resolved_account_id: int,
        shadow_bundle: Dict[str, Any],
        legacy_account_row: Any,
        legacy_broker_connection_rows: List[Any],
        legacy_sync_state_row: Any,
        legacy_sync_position_rows: List[Any],
        legacy_sync_cash_balance_rows: List[Any],
    ) -> Dict[str, Any]:
        shadow_account_payload = self._phase_f_normalize_compare_time_fields(
            dict(shadow_bundle.get("account") or {}),
            fields=("created_at", "updated_at"),
        )
        shadow_broker_connection_payloads = [
            self._phase_f_normalize_compare_time_fields(
                dict(row or {}),
                fields=("last_imported_at", "created_at", "updated_at"),
            )
            for row in list(shadow_bundle.get("broker_connections") or [])
        ]
        shadow_sync_state_payload = (
            self._phase_f_normalize_compare_time_fields(
                dict(shadow_bundle.get("sync_state") or {}),
                fields=("snapshot_date", "synced_at", "created_at", "updated_at"),
            )
            if shadow_bundle.get("sync_state") is not None
            else None
        )
        shadow_sync_position_payloads = [
            self._phase_f_normalize_compare_time_fields(
                dict(row or {}),
                fields=("created_at", "updated_at"),
            )
            for row in list(shadow_bundle.get("sync_positions") or [])
        ]
        shadow_sync_cash_balance_payloads = [
            self._phase_f_normalize_compare_time_fields(
                dict(row or {}),
                fields=("created_at", "updated_at"),
            )
            for row in list(shadow_bundle.get("sync_cash_balances") or [])
        ]

        legacy_account_payload = (
            self._phase_f_shadow_account_payload(legacy_account_row)
            if legacy_account_row is not None
            else None
        )
        legacy_broker_connection_payloads = [
            self._phase_f_shadow_broker_connection_payload(row) for row in legacy_broker_connection_rows
        ]
        legacy_sync_state_payload = (
            self._phase_f_shadow_sync_state_payload(legacy_sync_state_row)
            if legacy_sync_state_row is not None
            else None
        )
        legacy_sync_position_payloads = [
            self._phase_f_shadow_sync_position_payload(row) for row in legacy_sync_position_rows
        ]
        legacy_sync_cash_balance_payloads = [
            self._phase_f_shadow_sync_cash_balance_payload(row) for row in legacy_sync_cash_balance_rows
        ]
        if legacy_sync_state_row is not None:
            for payload in legacy_sync_position_payloads:
                payload["portfolio_sync_state_id"] = int(legacy_sync_state_row.id)
            for payload in legacy_sync_cash_balance_payloads:
                payload["portfolio_sync_state_id"] = int(legacy_sync_state_row.id)

        drift_reasons: List[str] = []
        surface_trust = {
            "account_metadata": "shadow_matches_legacy",
            "broker_connection_list": "shadow_matches_legacy",
            "latest_sync_overlay": "shadow_matches_legacy",
        }

        account_metadata_ready = legacy_account_payload is not None and shadow_account_payload == legacy_account_payload
        if legacy_account_payload is None:
            surface_trust["account_metadata"] = "legacy_missing"
            drift_reasons.append("account_row_missing")
        elif shadow_account_payload != legacy_account_payload:
            surface_trust["account_metadata"] = "shadow_drift"
            drift_reasons.append("account_row_payload_mismatch")

        broker_connection_list_ready = False
        if len(legacy_broker_connection_payloads) != len(shadow_broker_connection_payloads):
            surface_trust["broker_connection_list"] = "shadow_drift"
            drift_reasons.append("broker_connections_count_mismatch")
        elif legacy_broker_connection_payloads != shadow_broker_connection_payloads:
            surface_trust["broker_connection_list"] = "shadow_drift"
            drift_reasons.append("broker_connections_payload_mismatch")
        else:
            broker_connection_list_ready = account_metadata_ready

        latest_sync_overlay_ready = False
        if legacy_sync_state_payload is None and shadow_sync_state_payload is None:
            latest_sync_overlay_ready = broker_connection_list_ready
        elif legacy_sync_state_payload is None or shadow_sync_state_payload is None:
            surface_trust["latest_sync_overlay"] = "shadow_drift"
            drift_reasons.append("sync_state_count_mismatch")
        elif legacy_sync_state_payload != shadow_sync_state_payload:
            surface_trust["latest_sync_overlay"] = "shadow_drift"
            drift_reasons.append("sync_state_payload_mismatch")
        elif legacy_sync_position_payloads != shadow_sync_position_payloads:
            surface_trust["latest_sync_overlay"] = "shadow_drift"
            drift_reasons.append("sync_positions_payload_mismatch")
        elif legacy_sync_cash_balance_payloads != shadow_sync_cash_balance_payloads:
            surface_trust["latest_sync_overlay"] = "shadow_drift"
            drift_reasons.append("sync_cash_balances_payload_mismatch")
        else:
            latest_sync_overlay_ready = broker_connection_list_ready

        return {
            "shadow_account_id": resolved_account_id,
            "legacy_row_counts": {
                "broker_connections": len(legacy_broker_connection_payloads),
                "sync_positions": len(legacy_sync_position_payloads),
                "sync_cash_balances": len(legacy_sync_cash_balance_payloads),
            },
            "shadow_row_counts": {
                "broker_connections": len(shadow_broker_connection_payloads),
                "sync_positions": len(shadow_sync_position_payloads),
                "sync_cash_balances": len(shadow_sync_cash_balance_payloads),
            },
            "observed_readiness": {
                "account_row": legacy_account_payload is not None and bool(shadow_account_payload),
                "broker_connections": True,
                "sync_state": legacy_sync_state_payload is not None and shadow_sync_state_payload is not None,
            },
            "effective_readiness": {
                "account_metadata": account_metadata_ready,
                "broker_connection_list": broker_connection_list_ready,
                "latest_sync_overlay": latest_sync_overlay_ready,
            },
            "surface_trust": surface_trust,
            "drift_reasons": drift_reasons,
        }

    def _collect_phase_f_portfolio_shadow_authority_states(
        self,
        *,
        account_ids: Iterable[int],
        shadow_bundles_by_id: Optional[Dict[int, Dict[str, Any]]] = None,
    ) -> Dict[int, Optional[Dict[str, Any]]]:
        if not self._phase_f_enabled or self._phase_f_store is None:
            return {}

        resolved_account_ids = sorted({int(account_id) for account_id in account_ids if account_id is not None})
        if not resolved_account_ids:
            return {}

        if shadow_bundles_by_id is None:
            shadow_bundles_by_id = self._phase_f_store.get_account_shadow_bundles(account_ids=resolved_account_ids)
        authority_by_account_id: Dict[int, Optional[Dict[str, Any]]] = {
            account_id: None for account_id in resolved_account_ids
        }
        available_account_ids = [
            account_id for account_id in resolved_account_ids if shadow_bundles_by_id.get(account_id) is not None
        ]
        if not available_account_ids:
            return authority_by_account_id

        with self.get_session() as session:
            legacy_account_rows = session.execute(
                select(PortfolioAccount)
                .where(PortfolioAccount.id.in_(available_account_ids))
                .order_by(PortfolioAccount.id.asc())
            ).scalars().all()
            legacy_account_by_id = {int(row.id): row for row in legacy_account_rows}

            legacy_broker_connection_rows = session.execute(
                select(PortfolioBrokerConnection)
                .where(PortfolioBrokerConnection.portfolio_account_id.in_(available_account_ids))
                .order_by(
                    PortfolioBrokerConnection.portfolio_account_id.asc(),
                    PortfolioBrokerConnection.id.asc(),
                )
            ).scalars().all()
            legacy_broker_connections_by_account: Dict[int, List[Any]] = {
                account_id: [] for account_id in available_account_ids
            }
            for row in legacy_broker_connection_rows:
                legacy_broker_connections_by_account.setdefault(int(row.portfolio_account_id), []).append(row)

            legacy_sync_state_candidates = session.execute(
                select(PortfolioBrokerSyncState)
                .where(PortfolioBrokerSyncState.portfolio_account_id.in_(available_account_ids))
                .order_by(
                    PortfolioBrokerSyncState.portfolio_account_id.asc(),
                    PortfolioBrokerSyncState.synced_at.desc(),
                    PortfolioBrokerSyncState.id.desc(),
                )
            ).scalars().all()
            legacy_sync_state_by_account: Dict[int, Any] = {}
            for row in legacy_sync_state_candidates:
                account_id = int(row.portfolio_account_id)
                if account_id not in legacy_sync_state_by_account:
                    legacy_sync_state_by_account[account_id] = row

            broker_connection_ids = sorted(
                {
                    int(row.broker_connection_id)
                    for row in legacy_sync_state_by_account.values()
                    if getattr(row, "broker_connection_id", None) is not None
                }
            )
            legacy_sync_positions_by_broker_connection: Dict[int, List[Any]] = {
                connection_id: [] for connection_id in broker_connection_ids
            }
            legacy_sync_cash_balances_by_broker_connection: Dict[int, List[Any]] = {
                connection_id: [] for connection_id in broker_connection_ids
            }
            if broker_connection_ids:
                legacy_sync_position_rows = session.execute(
                    select(PortfolioBrokerSyncPosition)
                    .where(PortfolioBrokerSyncPosition.broker_connection_id.in_(broker_connection_ids))
                    .order_by(
                        PortfolioBrokerSyncPosition.broker_connection_id.asc(),
                        PortfolioBrokerSyncPosition.symbol.asc(),
                        PortfolioBrokerSyncPosition.id.asc(),
                    )
                ).scalars().all()
                for row in legacy_sync_position_rows:
                    legacy_sync_positions_by_broker_connection.setdefault(
                        int(row.broker_connection_id),
                    ).append(row)

                legacy_sync_cash_balance_rows = session.execute(
                    select(PortfolioBrokerSyncCashBalance)
                    .where(PortfolioBrokerSyncCashBalance.broker_connection_id.in_(broker_connection_ids))
                    .order_by(
                        PortfolioBrokerSyncCashBalance.broker_connection_id.asc(),
                        PortfolioBrokerSyncCashBalance.currency.asc(),
                        PortfolioBrokerSyncCashBalance.id.asc(),
                    )
                ).scalars().all()
                for row in legacy_sync_cash_balance_rows:
                    legacy_sync_cash_balances_by_broker_connection.setdefault(
                        int(row.broker_connection_id),
                    ).append(row)

        for account_id in available_account_ids:
            legacy_sync_state_row = legacy_sync_state_by_account.get(account_id)
            broker_connection_id = (
                int(legacy_sync_state_row.broker_connection_id)
                if legacy_sync_state_row is not None and getattr(legacy_sync_state_row, "broker_connection_id", None) is not None
                else None
            )
            authority_by_account_id[account_id] = self._build_phase_f_portfolio_shadow_authority_state(
                resolved_account_id=account_id,
                shadow_bundle=dict(shadow_bundles_by_id.get(account_id) or {}),
                legacy_account_row=legacy_account_by_id.get(account_id),
                legacy_broker_connection_rows=list(legacy_broker_connections_by_account.get(account_id, [])),
                legacy_sync_state_row=legacy_sync_state_row,
                legacy_sync_position_rows=(
                    list(legacy_sync_positions_by_broker_connection.get(broker_connection_id, []))
                    if broker_connection_id is not None
                    else []
                ),
                legacy_sync_cash_balance_rows=(
                    list(legacy_sync_cash_balances_by_broker_connection.get(broker_connection_id, []))
                    if broker_connection_id is not None
                    else []
                ),
            )

        return authority_by_account_id

    def get_phase_f_portfolio_shadow_authority_state(self, *, account_id: int) -> Optional[Dict[str, Any]]:
        return self._collect_phase_f_portfolio_shadow_authority_states(account_ids=[account_id]).get(int(account_id))

    def list_phase_f_portfolio_account_metadata_rows(
        self,
        *,
        include_inactive: bool = False,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> Optional[List[Any]]:
        if not self._phase_f_enabled or self._phase_f_store is None:
            return None

        resolved_owner_id = None if include_all_owners else self.require_user_id(owner_id)
        rows = self._phase_f_store.list_account_rows(
            owner_user_id=resolved_owner_id,
            include_inactive=include_inactive,
        )
        authority_by_account_id = self._collect_phase_f_portfolio_shadow_authority_states(
            account_ids=[int(row.id) for row in rows]
        )
        for row in rows:
            current_account_id = int(row.id)
            authority = authority_by_account_id.get(current_account_id)
            if authority is None:
                return None
            if not authority["effective_readiness"].get("account_metadata"):
                return None
            if resolved_owner_id is not None and str(getattr(row, "owner_user_id", "") or "") != resolved_owner_id:
                return None
        return [self._phase_f_account_metadata_row(row) for row in rows]

    def get_phase_f_portfolio_shadow_bundle(self, *, account_id: int) -> Optional[Dict[str, Any]]:
        if not self._phase_f_enabled or self._phase_f_store is None:
            return None
        return self._phase_f_store.get_account_shadow_bundle(account_id=int(account_id))

    def list_phase_f_portfolio_broker_connection_metadata_rows(
        self,
        *,
        portfolio_account_id: Optional[int] = None,
        broker_type: Optional[str] = None,
        status: Optional[str] = None,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> Optional[List[Any]]:
        if not self._phase_f_enabled or self._phase_f_store is None:
            return None

        resolved_owner_id = None if include_all_owners or owner_id is None else self.require_user_id(owner_id)
        rows = self._phase_f_store.list_broker_connection_rows(
            owner_user_id=resolved_owner_id,
            portfolio_account_id=int(portfolio_account_id) if portfolio_account_id is not None else None,
            broker_type=broker_type,
            status=status,
        )

        account_ids = sorted({int(row.portfolio_account_id) for row in rows})
        if portfolio_account_id is not None:
            account_ids = sorted({int(portfolio_account_id), *account_ids})

        account_rows = self._phase_f_store.list_account_rows(
            owner_user_id=resolved_owner_id,
            include_inactive=True,
        )
        account_name_by_id = {int(row.id): str(getattr(row, "name", "") or "") for row in account_rows}
        account_owner_by_id = {int(row.id): str(getattr(row, "owner_user_id", "") or "") for row in account_rows}
        authority_by_account_id = self._collect_phase_f_portfolio_shadow_authority_states(
            account_ids=account_ids
        )

        for current_account_id in account_ids:
            authority = authority_by_account_id.get(current_account_id)
            if authority is None:
                return None
            if not authority["effective_readiness"].get("account_metadata"):
                return None
            if not authority["effective_readiness"].get("broker_connection_list"):
                return None
            if resolved_owner_id is not None and account_owner_by_id.get(current_account_id) != resolved_owner_id:
                return None

        return [
            self._phase_f_broker_connection_metadata_row(
                row,
                portfolio_account_name=account_name_by_id.get(int(row.portfolio_account_id)),
            )
            for row in rows
        ]

    def get_phase_f_latest_broker_sync_state_bundle(
        self,
        *,
        portfolio_account_id: int,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> Optional[Dict[str, Any]]:
        if not self._phase_f_enabled or self._phase_f_store is None:
            return None

        resolved_owner_id = None if include_all_owners or owner_id is None else self.require_user_id(owner_id)
        shadow_bundles_by_id = self._phase_f_store.get_account_shadow_bundles(
            account_ids=[int(portfolio_account_id)]
        )
        authority = self._collect_phase_f_portfolio_shadow_authority_states(
            account_ids=[int(portfolio_account_id)],
            shadow_bundles_by_id=shadow_bundles_by_id,
        ).get(int(portfolio_account_id))
        if authority is None:
            return None
        if not authority["effective_readiness"].get("account_metadata"):
            return None
        if not authority["effective_readiness"].get("latest_sync_overlay"):
            return None

        shadow_bundle = shadow_bundles_by_id.get(int(portfolio_account_id))
        if shadow_bundle is None:
            return None
        shadow_account = dict(shadow_bundle.get("account") or {})
        if resolved_owner_id is not None and str(shadow_account.get("owner_user_id", "") or "") != resolved_owner_id:
            return None

        state_row = shadow_bundle.get("sync_state")
        if state_row is None:
            return None

        return {
            "state_row": self._phase_f_broker_sync_state_row(state_row),
            "positions": [
                self._phase_f_broker_sync_position_row(row)
                for row in list(shadow_bundle.get("sync_positions") or [])
            ],
            "cash_balances": [
                self._phase_f_broker_sync_cash_balance_row(row)
                for row in list(shadow_bundle.get("sync_cash_balances") or [])
            ],
        }

    @staticmethod
    def _phase_f_ledger_entry_types() -> Tuple[str, ...]:
        return ("cash", "corporate_action", "trade")

    @staticmethod
    def _phase_f_ledger_event_time(*, value: Any, entry_type: str) -> str:
        if isinstance(value, datetime):
            normalized_value = value.replace(tzinfo=None) if value.tzinfo is not None else value
            return normalized_value.isoformat()
        if isinstance(value, date):
            second_by_type = {
                "cash": 0,
                "corporate_action": 1,
                "trade": 2,
                "adjustment": 3,
            }
            return datetime.combine(value, time(0, 0, second_by_type.get(str(entry_type or ""), 0))).isoformat()
        if value is None:
            return ""
        raw_value = str(value)
        try:
            parsed = datetime.fromisoformat(raw_value)
        except ValueError:
            return raw_value
        if parsed.tzinfo is not None:
            parsed = parsed.replace(tzinfo=None)
        return parsed.isoformat()

    @staticmethod
    def _phase_f_normalize_ledger_payload_json(payload: Dict[str, Any], *, entry_type: str) -> Dict[str, Any]:
        normalized_payload = dict(payload or {})
        if entry_type == "trade":
            return {
                "legacy_table": normalized_payload.get("legacy_table"),
                "legacy_row_id": int(normalized_payload.get("legacy_row_id") or 0),
                "trade_uid": normalized_payload.get("trade_uid"),
                "side": normalized_payload.get("side"),
                "quantity": (
                    float(normalized_payload.get("quantity"))
                    if normalized_payload.get("quantity") is not None
                    else None
                ),
                "price": (
                    float(normalized_payload.get("price"))
                    if normalized_payload.get("price") is not None
                    else None
                ),
                "fee": (
                    float(normalized_payload.get("fee"))
                    if normalized_payload.get("fee") is not None
                    else None
                ),
                "tax": (
                    float(normalized_payload.get("tax"))
                    if normalized_payload.get("tax") is not None
                    else None
                ),
                "note": normalized_payload.get("note"),
            }
        if entry_type == "cash":
            return {
                "legacy_table": normalized_payload.get("legacy_table"),
                "legacy_row_id": int(normalized_payload.get("legacy_row_id") or 0),
                "direction": normalized_payload.get("direction"),
                "amount": (
                    float(normalized_payload.get("amount"))
                    if normalized_payload.get("amount") is not None
                    else None
                ),
                "currency": normalized_payload.get("currency"),
                "note": normalized_payload.get("note"),
            }
        if entry_type == "corporate_action":
            return {
                "legacy_table": normalized_payload.get("legacy_table"),
                "legacy_row_id": int(normalized_payload.get("legacy_row_id") or 0),
                "action_type": normalized_payload.get("action_type"),
                "cash_dividend_per_share": (
                    float(normalized_payload.get("cash_dividend_per_share"))
                    if normalized_payload.get("cash_dividend_per_share") is not None
                    else None
                ),
                "split_ratio": (
                    float(normalized_payload.get("split_ratio"))
                    if normalized_payload.get("split_ratio") is not None
                    else None
                ),
                "note": normalized_payload.get("note"),
            }
        return dict(normalized_payload)

    @classmethod
    def _phase_f_legacy_trade_ledger_payload(cls, row: Any) -> Dict[str, Any]:
        payload_json = cls._phase_f_normalize_ledger_payload_json(
            {
                "legacy_table": "portfolio_trades",
                "legacy_row_id": int(getattr(row, "id", 0) or 0),
                "trade_uid": getattr(row, "trade_uid", None),
                "side": getattr(row, "side", None),
                "quantity": getattr(row, "quantity", None),
                "price": getattr(row, "price", None),
                "fee": getattr(row, "fee", None),
                "tax": getattr(row, "tax", None),
                "note": getattr(row, "note", None),
            },
            entry_type="trade",
        )
        return {
            "id": int(phase_f_ledger_shadow_id("trade", int(getattr(row, "id", 0) or 0))),
            "entry_type": "trade",
            "event_time": cls._phase_f_ledger_event_time(
                value=getattr(row, "trade_date", None),
                entry_type="trade",
            ),
            "canonical_symbol": getattr(row, "symbol", None),
            "market": getattr(row, "market", None),
            "currency": getattr(row, "currency", None),
            "direction": getattr(row, "side", None),
            "quantity": float(getattr(row, "quantity", 0.0) or 0.0),
            "price": float(getattr(row, "price", 0.0) or 0.0),
            "amount": None,
            "fee": float(getattr(row, "fee", 0.0) or 0.0),
            "tax": float(getattr(row, "tax", 0.0) or 0.0),
            "corporate_action_type": None,
            "external_ref": getattr(row, "trade_uid", None),
            "dedup_hash": getattr(row, "dedup_hash", None),
            "note": getattr(row, "note", None),
            "payload_json": payload_json,
        }

    @classmethod
    def _phase_f_legacy_cash_ledger_payload(cls, row: Any) -> Dict[str, Any]:
        payload_json = cls._phase_f_normalize_ledger_payload_json(
            {
                "legacy_table": "portfolio_cash_ledger",
                "legacy_row_id": int(getattr(row, "id", 0) or 0),
                "direction": getattr(row, "direction", None),
                "amount": getattr(row, "amount", None),
                "currency": getattr(row, "currency", None),
                "note": getattr(row, "note", None),
            },
            entry_type="cash",
        )
        return {
            "id": int(phase_f_ledger_shadow_id("cash", int(getattr(row, "id", 0) or 0))),
            "entry_type": "cash",
            "event_time": cls._phase_f_ledger_event_time(
                value=getattr(row, "event_date", None),
                entry_type="cash",
            ),
            "canonical_symbol": None,
            "market": None,
            "currency": getattr(row, "currency", None),
            "direction": getattr(row, "direction", None),
            "quantity": None,
            "price": None,
            "amount": float(getattr(row, "amount", 0.0) or 0.0),
            "fee": None,
            "tax": None,
            "corporate_action_type": None,
            "external_ref": None,
            "dedup_hash": None,
            "note": getattr(row, "note", None),
            "payload_json": payload_json,
        }

    @classmethod
    def _phase_f_legacy_corporate_action_ledger_payload(cls, row: Any) -> Dict[str, Any]:
        payload_json = cls._phase_f_normalize_ledger_payload_json(
            {
                "legacy_table": "portfolio_corporate_actions",
                "legacy_row_id": int(getattr(row, "id", 0) or 0),
                "action_type": getattr(row, "action_type", None),
                "cash_dividend_per_share": getattr(row, "cash_dividend_per_share", None),
                "split_ratio": getattr(row, "split_ratio", None),
                "note": getattr(row, "note", None),
            },
            entry_type="corporate_action",
        )
        return {
            "id": int(
                phase_f_ledger_shadow_id("corporate_action", int(getattr(row, "id", 0) or 0))
            ),
            "entry_type": "corporate_action",
            "event_time": cls._phase_f_ledger_event_time(
                value=getattr(row, "effective_date", None),
                entry_type="corporate_action",
            ),
            "canonical_symbol": getattr(row, "symbol", None),
            "market": getattr(row, "market", None),
            "currency": getattr(row, "currency", None),
            "direction": None,
            "quantity": None,
            "price": None,
            "amount": None,
            "fee": None,
            "tax": None,
            "corporate_action_type": getattr(row, "action_type", None),
            "external_ref": None,
            "dedup_hash": None,
            "note": getattr(row, "note", None),
            "payload_json": payload_json,
        }

    @classmethod
    def _phase_f_normalize_shadow_ledger_payload(cls, row: Dict[str, Any]) -> Dict[str, Any]:
        entry_type = str(row.get("entry_type", "") or "")
        return {
            "id": int(row.get("id") or 0),
            "entry_type": entry_type,
            "event_time": cls._phase_f_ledger_event_time(value=row.get("event_time"), entry_type=entry_type),
            "canonical_symbol": row.get("canonical_symbol"),
            "market": row.get("market"),
            "currency": row.get("currency"),
            "direction": row.get("direction"),
            "quantity": float(row.get("quantity")) if row.get("quantity") is not None else None,
            "price": float(row.get("price")) if row.get("price") is not None else None,
            "amount": float(row.get("amount")) if row.get("amount") is not None else None,
            "fee": float(row.get("fee")) if row.get("fee") is not None else None,
            "tax": float(row.get("tax")) if row.get("tax") is not None else None,
            "corporate_action_type": row.get("corporate_action_type"),
            "external_ref": row.get("external_ref"),
            "dedup_hash": row.get("dedup_hash"),
            "note": row.get("note"),
            "payload_json": cls._phase_f_normalize_ledger_payload_json(
                cls._phase_f_json_payload(row.get("payload_json")),
                entry_type=entry_type,
            ),
        }

    @classmethod
    def _build_phase_f_legacy_ledger_payloads(cls, projection: Dict[str, Any]) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for row in list(projection.get("cash_rows") or []):
            rows.append(cls._phase_f_legacy_cash_ledger_payload(row))
        for row in list(projection.get("corporate_action_rows") or []):
            rows.append(cls._phase_f_legacy_corporate_action_ledger_payload(row))
        for row in list(projection.get("trade_rows") or []):
            rows.append(cls._phase_f_legacy_trade_ledger_payload(row))
        return sorted(
            rows,
            key=lambda item: (
                str(item.get("event_time") or ""),
                int(item.get("id") or 0),
            ),
        )

    @classmethod
    def _build_phase_f_shadow_ledger_payloads(cls, shadow_bundle: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        rows = [cls._phase_f_normalize_shadow_ledger_payload(row) for row in list((shadow_bundle or {}).get("ledger") or [])]
        return sorted(
            rows,
            key=lambda item: (
                str(item.get("event_time") or ""),
                int(item.get("id") or 0),
            ),
        )

    @classmethod
    def _phase_f_count_ledger_event_types(cls, rows: List[Dict[str, Any]]) -> Dict[str, int]:
        counts = {entry_type: 0 for entry_type in cls._phase_f_ledger_entry_types()}
        for row in rows:
            entry_type = str(row.get("entry_type", "") or "")
            if entry_type in counts:
                counts[entry_type] += 1
        return counts

    @staticmethod
    def _phase_f_first_ledger_payload_mismatch(
        legacy_rows: List[Dict[str, Any]],
        shadow_rows: List[Dict[str, Any]],
    ) -> Tuple[Optional[int], Optional[str], Optional[str]]:
        for index, (legacy_row, shadow_row) in enumerate(zip(legacy_rows, shadow_rows)):
            if legacy_row != shadow_row:
                return (
                    index,
                    str(legacy_row.get("entry_type", "") or ""),
                    str(shadow_row.get("entry_type", "") or ""),
                )
        return (None, None, None)

    def _build_phase_f_ledger_event_payload_authority_state(
        self,
        *,
        account_id: int,
        projection: Dict[str, Any],
        shadow_bundle: Optional[Dict[str, Any]],
        shadow_authority_state: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        account_row = projection.get("account_row")
        legacy_rows = self._build_phase_f_legacy_ledger_payloads(projection)
        shadow_rows = self._build_phase_f_shadow_ledger_payloads(shadow_bundle)
        legacy_counts = self._phase_f_count_ledger_event_types(legacy_rows)
        shadow_counts = self._phase_f_count_ledger_event_types(shadow_rows)
        representative_shapes = [
            entry_type
            for entry_type in self._phase_f_ledger_entry_types()
            if legacy_counts[entry_type] > 0 and shadow_counts[entry_type] > 0
        ]
        missing_shapes = [
            entry_type
            for entry_type in self._phase_f_ledger_entry_types()
            if entry_type not in representative_shapes
        ]

        first_mismatch_index, legacy_entry_type_at_mismatch, shadow_entry_type_at_mismatch = (
            self._phase_f_first_ledger_payload_mismatch(legacy_rows, shadow_rows)
        )
        payload_parity_observed = bool(legacy_rows) and legacy_rows == shadow_rows
        legacy_total_rows = len(legacy_rows)
        shadow_total_rows = len(shadow_rows)
        account_metadata_authority_ready = bool(
            shadow_authority_state and shadow_authority_state["effective_readiness"].get("account_metadata")
        )

        if legacy_total_rows == 0:
            current_signal = "no_events_present"
            blocked_reasons = ["legacy_event_history_missing"]
        elif shadow_total_rows == 0:
            current_signal = "shadow_missing"
            blocked_reasons = ["shadow_ledger_missing"]
        elif legacy_counts != shadow_counts or legacy_total_rows != shadow_total_rows:
            current_signal = "count_mismatch"
            blocked_reasons = ["ledger_event_count_mismatch"]
        elif not payload_parity_observed:
            current_signal = "payload_drift"
            blocked_reasons = ["event_payload_parity_not_observed"]
        elif not account_metadata_authority_ready:
            current_signal = "payload_parity_observed"
            blocked_reasons = ["account_metadata_authority_missing"]
        else:
            current_signal = "payload_parity_observed"
            blocked_reasons = []

        if payload_parity_observed and account_metadata_authority_ready:
            authority_prerequisite_state = "authority_ready"
            authority_ready = True
        elif payload_parity_observed:
            authority_prerequisite_state = "observed_only"
            authority_ready = False
        else:
            authority_prerequisite_state = "blocked"
            authority_ready = False

        if current_signal == "payload_parity_observed":
            if len(representative_shapes) >= 3:
                audit_signal = "representative_parity_observed"
                evidence_coverage_state = "representative"
                operational_confidence_state = "representative"
                design_prerequisite_support = "stronger_operational_evidence"
            else:
                audit_signal = "narrow_parity_observed"
                evidence_coverage_state = "narrow"
                operational_confidence_state = "narrow"
                design_prerequisite_support = "limited_observation_only"
        elif current_signal == "count_mismatch":
            audit_signal = "count_mismatch_visible"
            evidence_coverage_state = "narrow"
            operational_confidence_state = "blocked"
            design_prerequisite_support = "blocked"
        elif current_signal == "payload_drift":
            audit_signal = "payload_drift_visible"
            evidence_coverage_state = "narrow"
            operational_confidence_state = "blocked"
            design_prerequisite_support = "blocked"
        elif current_signal == "shadow_missing":
            audit_signal = "shadow_missing_visible"
            evidence_coverage_state = "narrow"
            operational_confidence_state = "blocked"
            design_prerequisite_support = "blocked"
        else:
            audit_signal = "legacy_history_missing"
            evidence_coverage_state = "none"
            operational_confidence_state = "blocked"
            design_prerequisite_support = "blocked"

        return {
            "account_id": int(account_id),
            "owner_user_id": str(getattr(account_row, "owner_id", "") or ""),
            "account_name": str(getattr(account_row, "name", "") or ""),
            "authority_model": "phase_f_ledger_event_payload_authority_v1",
            "phase_f_authority_model": "phase_f_projection_compare",
            "current_signal": current_signal,
            "payload_parity_observed": payload_parity_observed,
            "authority_prerequisite_state": authority_prerequisite_state,
            "authority_ready": authority_ready,
            "runtime_cutover_ready": False,
            "future_authority_scope": "event_history_and_replay_input_design",
            "blocked_reasons": list(blocked_reasons),
            "missing_signals": list(blocked_reasons),
            "downstream_blockers": [
                "event_history_domain_authority_layer_required",
                "replay_as_of_subset_authority_missing",
            ],
            "account_metadata_authority_ready": account_metadata_authority_ready,
            "legacy_row_counts": {
                "total_event_rows": legacy_total_rows,
            },
            "shadow_row_counts": {
                "ledger_rows": shadow_total_rows,
            },
            "parity_evidence": {
                "legacy_event_type_counts": dict(legacy_counts),
                "shadow_event_type_counts": dict(shadow_counts),
                "legacy_event_types_present": [
                    entry_type for entry_type in self._phase_f_ledger_entry_types() if legacy_counts[entry_type] > 0
                ],
                "shadow_event_types_present": [
                    entry_type for entry_type in self._phase_f_ledger_entry_types() if shadow_counts[entry_type] > 0
                ],
                "representative_event_shapes_observed": list(representative_shapes),
                "event_type_count_parity_observed": legacy_counts == shadow_counts,
            },
            "drift_details": {
                "legacy_total_event_rows": legacy_total_rows,
                "shadow_total_event_rows": shadow_total_rows,
                "legacy_event_types_missing_in_shadow": [
                    entry_type
                    for entry_type in self._phase_f_ledger_entry_types()
                    if legacy_counts[entry_type] > 0 and shadow_counts[entry_type] == 0
                ],
                "shadow_event_types_missing_in_legacy": [
                    entry_type
                    for entry_type in self._phase_f_ledger_entry_types()
                    if shadow_counts[entry_type] > 0 and legacy_counts[entry_type] == 0
                ],
                "first_mismatch_index": first_mismatch_index,
                "legacy_entry_type_at_mismatch": legacy_entry_type_at_mismatch,
                "shadow_entry_type_at_mismatch": shadow_entry_type_at_mismatch,
            },
            "operational_audit": {
                "audit_signal": audit_signal,
                "evidence_coverage_state": evidence_coverage_state,
                "representative_event_shape_count": len(representative_shapes),
                "representative_event_shape_target": len(self._phase_f_ledger_entry_types()),
                "missing_representative_event_shapes": missing_shapes,
                "operational_confidence_state": operational_confidence_state,
                "design_prerequisite_support": design_prerequisite_support,
            },
        }

    def _build_phase_f_event_history_authority_state(
        self,
        *,
        account_id: int,
        ledger_authority_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        prerequisite_state = str(ledger_authority_state.get("authority_prerequisite_state", "") or "blocked")
        blocked_reasons = list(ledger_authority_state.get("blocked_reasons") or [])

        if prerequisite_state == "authority_ready":
            current_signal = "prerequisite_ready"
            current_blocked_reasons: List[str] = []
            authority_ready = True
        elif prerequisite_state == "observed_only":
            current_signal = "ledger_payload_observed_only"
            current_blocked_reasons = blocked_reasons
            authority_ready = False
        else:
            current_signal = "ledger_payload_blocked"
            current_blocked_reasons = blocked_reasons
            authority_ready = False

        return {
            "account_id": int(account_id),
            "owner_user_id": str(ledger_authority_state.get("owner_user_id", "") or ""),
            "account_name": str(ledger_authority_state.get("account_name", "") or ""),
            "authority_model": "phase_f_event_history_authority_v1",
            "phase_f_authority_model": "phase_f_projection_compare",
            "prerequisite_helper": "get_phase_f_ledger_event_payload_authority_state",
            "current_signal": current_signal,
            "authority_prerequisite_state": prerequisite_state,
            "authority_ready": authority_ready,
            "runtime_cutover_ready": False,
            "blocked_reasons": current_blocked_reasons,
            "missing_signals": list(current_blocked_reasons),
            "downstream_blockers": [
                "replay_input_cost_method_specific_authority_missing",
                "replay_input_lot_authority_missing",
                "replay_input_as_of_boundary_missing",
                "snapshot_cache_freshness_authority_missing",
                "runtime_pg_event_history_read_cutover_not_enabled",
            ],
        }

    def _build_phase_f_replay_input_authority_state(
        self,
        *,
        account_id: int,
        ledger_authority_state: Dict[str, Any],
        event_history_authority_state: Dict[str, Any],
        snapshot_cost_methods: List[str],
        legacy_snapshot_row_count: int,
        legacy_lot_row_count: int,
        shadow_position_row_count: int,
        replay_capabilities: Dict[str, bool],
    ) -> Dict[str, Any]:
        prerequisite_state = str(
            event_history_authority_state.get("authority_prerequisite_state", "") or "blocked"
        )
        replay_specific_readiness = {
            "cost_method_specific_authority": bool(
                replay_capabilities.get("cost_method_specific_authority", False)
            ),
            "lot_authority": bool(replay_capabilities.get("lot_authority", False)),
            "as_of_replay_boundary": bool(replay_capabilities.get("as_of_replay_boundary", False)),
        }

        if prerequisite_state == "authority_ready":
            blocked_reasons = [
                blocker
                for blocker, ready in [
                    ("cost_method_specific_authority_missing", replay_specific_readiness["cost_method_specific_authority"]),
                    ("lot_authority_missing", replay_specific_readiness["lot_authority"]),
                    ("as_of_replay_boundary_missing", replay_specific_readiness["as_of_replay_boundary"]),
                ]
                if not ready
            ]
            if blocked_reasons:
                current_signal = "replay_specific_gaps_observed"
                resolved_state = "observed_only"
                authority_ready = False
            else:
                current_signal = "prerequisite_ready"
                resolved_state = "authority_ready"
                authority_ready = True
        elif prerequisite_state == "observed_only":
            current_signal = "event_history_observed_only"
            resolved_state = "observed_only"
            blocked_reasons = list(event_history_authority_state.get("blocked_reasons") or [])
            authority_ready = False
        else:
            current_signal = "event_history_blocked"
            resolved_state = "blocked"
            blocked_reasons = list(event_history_authority_state.get("blocked_reasons") or [])
            authority_ready = False

        return {
            "account_id": int(account_id),
            "owner_user_id": str(ledger_authority_state.get("owner_user_id", "") or ""),
            "account_name": str(ledger_authority_state.get("account_name", "") or ""),
            "authority_model": "phase_f_replay_input_authority_v1",
            "phase_f_authority_model": "phase_f_projection_compare",
            "prerequisite_helper": "get_phase_f_event_history_authority_state",
            "current_signal": current_signal,
            "authority_prerequisite_state": resolved_state,
            "authority_ready": authority_ready,
            "runtime_cutover_ready": False,
            "blocked_reasons": list(blocked_reasons),
            "missing_signals": list(blocked_reasons),
            "downstream_blockers": [
                "snapshot_cache_freshness_authority_missing",
                "runtime_pg_replay_input_cutover_not_enabled",
            ],
            "snapshot_cost_methods": list(snapshot_cost_methods),
            "legacy_snapshot_row_count": int(legacy_snapshot_row_count),
            "legacy_lot_row_count": int(legacy_lot_row_count),
            "shadow_position_row_count": int(shadow_position_row_count),
            "replay_specific_readiness": replay_specific_readiness,
        }

    def _build_phase_f_snapshot_cache_authority_state(
        self,
        *,
        account_id: int,
        ledger_authority_state: Dict[str, Any],
        event_history_authority_state: Dict[str, Any],
        snapshot_cost_methods: List[str],
        legacy_snapshot_row_count: int,
        legacy_position_row_count: int,
        legacy_lot_row_count: int,
        shadow_position_row_count: int,
        snapshot_capabilities: Dict[str, bool],
    ) -> Dict[str, Any]:
        prerequisite_state = str(
            event_history_authority_state.get("authority_prerequisite_state", "") or "blocked"
        )
        snapshot_specific_readiness = {
            "snapshot_projection_authority": bool(
                snapshot_capabilities.get("snapshot_projection_authority", False)
            ),
            "lot_projection_authority": bool(snapshot_capabilities.get("lot_projection_authority", False)),
            "freshness_invalidation_authority": bool(
                snapshot_capabilities.get("freshness_invalidation_authority", False)
            ),
            "valuation_semantic_authority": bool(
                snapshot_capabilities.get("valuation_semantic_authority", False)
            ),
        }

        if prerequisite_state == "authority_ready":
            blocked_reasons = [
                blocker
                for blocker, ready in [
                    (
                        "snapshot_projection_authority_missing",
                        snapshot_specific_readiness["snapshot_projection_authority"],
                    ),
                    ("lot_projection_authority_missing", snapshot_specific_readiness["lot_projection_authority"]),
                    (
                        "snapshot_freshness_invalidation_authority_missing",
                        snapshot_specific_readiness["freshness_invalidation_authority"],
                    ),
                    (
                        "valuation_semantic_authority_missing",
                        snapshot_specific_readiness["valuation_semantic_authority"],
                    ),
                ]
                if not ready
            ]
            if blocked_reasons:
                current_signal = "snapshot_specific_gaps_observed"
                resolved_state = "observed_only"
                authority_ready = False
            else:
                current_signal = "prerequisite_ready"
                resolved_state = "authority_ready"
                authority_ready = True
        elif prerequisite_state == "observed_only":
            current_signal = "event_history_observed_only"
            resolved_state = "observed_only"
            blocked_reasons = list(event_history_authority_state.get("blocked_reasons") or [])
            authority_ready = False
        else:
            current_signal = "event_history_blocked"
            resolved_state = "blocked"
            blocked_reasons = list(event_history_authority_state.get("blocked_reasons") or [])
            authority_ready = False

        return {
            "account_id": int(account_id),
            "owner_user_id": str(ledger_authority_state.get("owner_user_id", "") or ""),
            "account_name": str(ledger_authority_state.get("account_name", "") or ""),
            "authority_model": "phase_f_snapshot_cache_authority_v1",
            "phase_f_authority_model": "phase_f_projection_compare",
            "prerequisite_helper": "get_phase_f_event_history_authority_state",
            "current_signal": current_signal,
            "authority_prerequisite_state": resolved_state,
            "authority_ready": authority_ready,
            "runtime_cutover_ready": False,
            "blocked_reasons": list(blocked_reasons),
            "missing_signals": list(blocked_reasons),
            "downstream_blockers": ["runtime_pg_snapshot_cache_cutover_not_enabled"],
            "snapshot_cost_methods": list(snapshot_cost_methods),
            "legacy_snapshot_row_count": int(legacy_snapshot_row_count),
            "legacy_position_row_count": int(legacy_position_row_count),
            "legacy_lot_row_count": int(legacy_lot_row_count),
            "shadow_position_row_count": int(shadow_position_row_count),
            "snapshot_specific_readiness": snapshot_specific_readiness,
        }

    @staticmethod
    def _build_phase_f_authority_summary_domain_state(
        *,
        state: Dict[str, Any],
        domain_specific_blockers: List[str],
        inherited_upstream_blockers: List[str],
    ) -> Dict[str, Any]:
        return {
            "authority_model": state.get("authority_model"),
            "current_signal": state.get("current_signal"),
            "authority_prerequisite_state": state.get("authority_prerequisite_state"),
            "authority_ready": bool(state.get("authority_ready", False)),
            "runtime_cutover_ready": bool(state.get("runtime_cutover_ready", False)),
            "domain_specific_blockers": list(domain_specific_blockers),
            "inherited_upstream_blockers": list(inherited_upstream_blockers),
            "has_domain_specific_blockers": bool(domain_specific_blockers),
            "blocked_only_by_upstream": (not domain_specific_blockers and bool(inherited_upstream_blockers)),
            "downstream_blockers": list(state.get("downstream_blockers") or []),
        }

    def _build_phase_f_effective_authority_summary(
        self,
        *,
        account_id: int,
        ledger_authority_state: Dict[str, Any],
        event_history_authority_state: Dict[str, Any],
        replay_input_authority_state: Dict[str, Any],
        snapshot_cache_authority_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        ledger_domain = self._build_phase_f_authority_summary_domain_state(
            state=ledger_authority_state,
            domain_specific_blockers=list(ledger_authority_state.get("missing_signals") or []),
            inherited_upstream_blockers=[],
        )
        ledger_ready = str(ledger_authority_state.get("authority_prerequisite_state", "")) == "authority_ready"
        event_history_domain = self._build_phase_f_authority_summary_domain_state(
            state=event_history_authority_state,
            domain_specific_blockers=[],
            inherited_upstream_blockers=[] if ledger_ready else list(ledger_authority_state.get("blocked_reasons") or []),
        )
        event_history_ready = (
            str(event_history_authority_state.get("authority_prerequisite_state", "")) == "authority_ready"
        )
        replay_domain = self._build_phase_f_authority_summary_domain_state(
            state=replay_input_authority_state,
            domain_specific_blockers=(
                list(replay_input_authority_state.get("blocked_reasons") or [])
                if event_history_ready
                else []
            ),
            inherited_upstream_blockers=(
                []
                if event_history_ready
                else list(event_history_authority_state.get("blocked_reasons") or [])
            ),
        )
        snapshot_domain = self._build_phase_f_authority_summary_domain_state(
            state=snapshot_cache_authority_state,
            domain_specific_blockers=(
                list(snapshot_cache_authority_state.get("blocked_reasons") or [])
                if event_history_ready
                else []
            ),
            inherited_upstream_blockers=(
                []
                if event_history_ready
                else list(event_history_authority_state.get("blocked_reasons") or [])
            ),
        )

        domains = {
            "ledger_event_payload_parity": ledger_domain,
            "event_history_authority": event_history_domain,
            "replay_input_authority": replay_domain,
            "snapshot_cache_authority": snapshot_domain,
        }
        domain_order = [
            "event_history_authority",
            "ledger_event_payload_parity",
            "replay_input_authority",
            "snapshot_cache_authority",
        ]

        next_unmet_boundary = None
        if not ledger_domain["authority_ready"]:
            next_unmet_boundary = {
                "domain": "ledger_event_payload_parity",
                "reason": "foundational_boundary_not_ready",
            }
        elif replay_domain["has_domain_specific_blockers"]:
            next_unmet_boundary = {
                "domain": "replay_input_authority",
                "reason": "domain_specific_blockers_remaining",
            }
        elif snapshot_domain["has_domain_specific_blockers"]:
            next_unmet_boundary = {
                "domain": "snapshot_cache_authority",
                "reason": "domain_specific_blockers_remaining",
            }

        effective_readiness = {
            "authority_ready_domains": [
                domain for domain in domain_order if domains[domain]["authority_ready"]
            ],
            "observed_only_domains": [
                domain
                for domain in domain_order
                if domains[domain]["authority_prerequisite_state"] == "observed_only"
            ],
            "blocked_domains": [
                domain for domain in domain_order if domains[domain]["authority_prerequisite_state"] == "blocked"
            ],
            "domains_blocked_only_by_upstream": [
                domain for domain in domain_order if domains[domain]["blocked_only_by_upstream"]
            ],
            "domains_with_domain_specific_blockers": [
                domain for domain in domain_order if domains[domain]["has_domain_specific_blockers"]
            ],
            "runtime_cutover_ready": all(domains[domain]["runtime_cutover_ready"] for domain in domain_order),
            "domains_with_runtime_cutover_disabled": [
                domain for domain in domain_order if not domains[domain]["runtime_cutover_ready"]
            ],
        }

        foundational_boundary = dict(domains["ledger_event_payload_parity"])
        foundational_boundary["domain"] = "ledger_event_payload_parity"

        return {
            "account_id": int(account_id),
            "authority_model": "phase_f_effective_authority_summary_v1",
            "highest_roi_category": "ledger_event_payload_parity",
            "foundational_boundary": foundational_boundary,
            "next_unmet_boundary": next_unmet_boundary,
            "effective_readiness": effective_readiness,
            "domains": domains,
        }

    def _build_phase_f_domain_readiness_gate(
        self,
        *,
        target_domain: str,
        effective_authority_summary: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        domains = dict(effective_authority_summary.get("domains") or {})
        target_state = domains.get(target_domain)
        if not isinstance(target_state, dict):
            return None

        if target_state.get("authority_ready"):
            gate_status = "design_prerequisite_ready"
            next_unmet_boundary = None
        elif target_state.get("blocked_only_by_upstream"):
            gate_status = "upstream_blocked"
            next_unmet_boundary = effective_authority_summary.get("next_unmet_boundary")
        else:
            gate_status = "domain_specific_blocked"
            summary_boundary = effective_authority_summary.get("next_unmet_boundary")
            if isinstance(summary_boundary, dict) and summary_boundary.get("domain") == target_domain:
                next_unmet_boundary = summary_boundary
            else:
                next_unmet_boundary = {
                    "domain": target_domain,
                    "reason": "domain_specific_blockers_remaining",
                }

        return {
            "gate_model": "phase_f_domain_readiness_gate_v1",
            "target_domain": target_domain,
            "gate_status": gate_status,
            "design_prerequisite_ready": bool(target_state.get("authority_ready", False)),
            "upstream_blocked": bool(target_state.get("blocked_only_by_upstream", False)),
            "has_domain_specific_blockers": bool(target_state.get("has_domain_specific_blockers", False)),
            "inherited_upstream_blockers": list(target_state.get("inherited_upstream_blockers") or []),
            "domain_specific_blockers": list(target_state.get("domain_specific_blockers") or []),
            "next_unmet_boundary": next_unmet_boundary,
            "runtime_cutover_ready": bool(target_state.get("runtime_cutover_ready", False)),
            "highest_roi_category": effective_authority_summary.get("highest_roi_category"),
            "target_domain_state": dict(target_state),
        }

    def get_phase_f_ledger_event_payload_authority_state(self, *, account_id: int) -> Optional[Dict[str, Any]]:
        if not self._phase_f_enabled or self._phase_f_store is None:
            return None

        resolved_account_id = int(account_id)
        with self.get_session() as session:
            projection = self._load_phase_f_portfolio_projection_in_session(
                session=session,
                account_id=resolved_account_id,
            )
        if projection is None:
            return None

        shadow_bundle = self._phase_f_store.get_account_shadow_bundle(account_id=resolved_account_id)
        shadow_authority_state = self.get_phase_f_portfolio_shadow_authority_state(account_id=resolved_account_id)
        return self._build_phase_f_ledger_event_payload_authority_state(
            account_id=resolved_account_id,
            projection=projection,
            shadow_bundle=shadow_bundle,
            shadow_authority_state=shadow_authority_state,
        )

    def get_phase_f_event_history_authority_state(self, *, account_id: int) -> Optional[Dict[str, Any]]:
        ledger_authority_state = self.get_phase_f_ledger_event_payload_authority_state(account_id=int(account_id))
        if ledger_authority_state is None:
            return None
        return self._build_phase_f_event_history_authority_state(
            account_id=int(account_id),
            ledger_authority_state=ledger_authority_state,
        )

    def get_phase_f_replay_input_authority_state(self, *, account_id: int) -> Optional[Dict[str, Any]]:
        if not self._phase_f_enabled or self._phase_f_store is None:
            return None

        resolved_account_id = int(account_id)
        ledger_authority_state = self.get_phase_f_ledger_event_payload_authority_state(account_id=resolved_account_id)
        event_history_authority_state = self.get_phase_f_event_history_authority_state(account_id=resolved_account_id)
        if ledger_authority_state is None or event_history_authority_state is None:
            return None

        with self.get_session() as session:
            projection = self._load_phase_f_portfolio_projection_in_session(
                session=session,
                account_id=resolved_account_id,
            )
            if projection is None:
                return None
            legacy_lot_row_count = int(
                session.execute(
                    select(func.count())
                    .select_from(PortfolioPositionLot)
                    .where(PortfolioPositionLot.account_id == resolved_account_id)
                ).scalar_one()
                or 0
            )

        shadow_bundle = self._phase_f_store.get_account_shadow_bundle(account_id=resolved_account_id)
        replay_capabilities = {
            "cost_method_specific_authority": False,
            "lot_authority": False,
            "as_of_replay_boundary": False,
        }
        snapshot_cost_methods = sorted(
            {
                str(getattr(row, "cost_method", "") or "").strip().lower()
                for row in list(projection.get("snapshot_rows") or [])
                if str(getattr(row, "cost_method", "") or "").strip()
            }
        )
        return self._build_phase_f_replay_input_authority_state(
            account_id=resolved_account_id,
            ledger_authority_state=ledger_authority_state,
            event_history_authority_state=event_history_authority_state,
            snapshot_cost_methods=snapshot_cost_methods,
            legacy_snapshot_row_count=len(list(projection.get("snapshot_rows") or [])),
            legacy_lot_row_count=legacy_lot_row_count,
            shadow_position_row_count=len(list((shadow_bundle or {}).get("positions") or [])),
            replay_capabilities=replay_capabilities,
        )

    def get_phase_f_snapshot_cache_authority_state(self, *, account_id: int) -> Optional[Dict[str, Any]]:
        if not self._phase_f_enabled or self._phase_f_store is None:
            return None

        resolved_account_id = int(account_id)
        ledger_authority_state = self.get_phase_f_ledger_event_payload_authority_state(account_id=resolved_account_id)
        event_history_authority_state = self.get_phase_f_event_history_authority_state(account_id=resolved_account_id)
        if ledger_authority_state is None or event_history_authority_state is None:
            return None

        with self.get_session() as session:
            projection = self._load_phase_f_portfolio_projection_in_session(
                session=session,
                account_id=resolved_account_id,
            )
            if projection is None:
                return None
            legacy_lot_row_count = int(
                session.execute(
                    select(func.count())
                    .select_from(PortfolioPositionLot)
                    .where(PortfolioPositionLot.account_id == resolved_account_id)
                ).scalar_one()
                or 0
            )

        shadow_bundle = self._phase_f_store.get_account_shadow_bundle(account_id=resolved_account_id)
        snapshot_capabilities = {
            "snapshot_projection_authority": False,
            "lot_projection_authority": False,
            "freshness_invalidation_authority": False,
            "valuation_semantic_authority": False,
        }
        snapshot_cost_methods = sorted(
            {
                str(getattr(row, "cost_method", "") or "").strip().lower()
                for row in list(projection.get("snapshot_rows") or [])
                if str(getattr(row, "cost_method", "") or "").strip()
            }
        )
        return self._build_phase_f_snapshot_cache_authority_state(
            account_id=resolved_account_id,
            ledger_authority_state=ledger_authority_state,
            event_history_authority_state=event_history_authority_state,
            snapshot_cost_methods=snapshot_cost_methods,
            legacy_snapshot_row_count=len(list(projection.get("snapshot_rows") or [])),
            legacy_position_row_count=len(list(projection.get("position_rows") or [])),
            legacy_lot_row_count=legacy_lot_row_count,
            shadow_position_row_count=len(list((shadow_bundle or {}).get("positions") or [])),
            snapshot_capabilities=snapshot_capabilities,
        )

    def get_phase_f_effective_authority_summary(self, *, account_id: int) -> Optional[Dict[str, Any]]:
        resolved_account_id = int(account_id)
        ledger_authority_state = self.get_phase_f_ledger_event_payload_authority_state(account_id=resolved_account_id)
        event_history_authority_state = self.get_phase_f_event_history_authority_state(account_id=resolved_account_id)
        replay_input_authority_state = self.get_phase_f_replay_input_authority_state(account_id=resolved_account_id)
        snapshot_cache_authority_state = self.get_phase_f_snapshot_cache_authority_state(account_id=resolved_account_id)
        if (
            ledger_authority_state is None
            or event_history_authority_state is None
            or replay_input_authority_state is None
            or snapshot_cache_authority_state is None
        ):
            return None

        return self._build_phase_f_effective_authority_summary(
            account_id=resolved_account_id,
            ledger_authority_state=ledger_authority_state,
            event_history_authority_state=event_history_authority_state,
            replay_input_authority_state=replay_input_authority_state,
            snapshot_cache_authority_state=snapshot_cache_authority_state,
        )

    def get_phase_f_domain_readiness_gate(
        self,
        *,
        account_id: int,
        target_domain: str,
    ) -> Optional[Dict[str, Any]]:
        effective_authority_summary = self.get_phase_f_effective_authority_summary(account_id=int(account_id))
        if effective_authority_summary is None:
            return None
        return self._build_phase_f_domain_readiness_gate(
            target_domain=str(target_domain or "").strip(),
            effective_authority_summary=effective_authority_summary,
        )

    def get_phase_f_portfolio_prerequisite_state(self, *, account_id: int) -> Optional[Dict[str, Any]]:
        resolved_account_id = int(account_id)
        ledger_authority_state = self.get_phase_f_ledger_event_payload_authority_state(account_id=resolved_account_id)
        event_history_authority_state = self.get_phase_f_event_history_authority_state(account_id=resolved_account_id)
        replay_input_authority_state = self.get_phase_f_replay_input_authority_state(account_id=resolved_account_id)
        snapshot_cache_authority_state = self.get_phase_f_snapshot_cache_authority_state(account_id=resolved_account_id)
        effective_authority_summary = self.get_phase_f_effective_authority_summary(account_id=resolved_account_id)
        if (
            ledger_authority_state is None
            or event_history_authority_state is None
            or replay_input_authority_state is None
            or snapshot_cache_authority_state is None
            or effective_authority_summary is None
        ):
            return None

        return {
            "account_id": resolved_account_id,
            "highest_roi_category": effective_authority_summary.get("highest_roi_category"),
            "categories": {
                "ledger_event_payload_parity": dict(ledger_authority_state),
                "replay_input_parity": dict(replay_input_authority_state),
                "snapshot_cache_freshness_parity": dict(snapshot_cache_authority_state),
            },
            "event_history_authority": dict(event_history_authority_state),
            "replay_input_authority": dict(replay_input_authority_state),
            "snapshot_cache_authority": dict(snapshot_cache_authority_state),
            "effective_authority_summary": dict(effective_authority_summary),
        }

    def get_phase_f_trade_list_comparison_candidate(
        self,
        *,
        account_id: Optional[int],
        date_from: Optional[date],
        date_to: Optional[date],
        symbol: Optional[str],
        side: Optional[str],
        page: int,
        page_size: int,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> Optional[Dict[str, Any]]:
        if not self._phase_f_enabled or self._phase_f_store is None:
            return None

        resolved_owner_id = None if include_all_owners else self.require_user_id(owner_id)
        return self._phase_f_store.query_trade_list_comparison_candidate(
            account_id=int(account_id) if account_id is not None else None,
            date_from=date_from,
            date_to=date_to,
            symbol=symbol,
            side=side,
            page=int(page),
            page_size=int(page_size),
            owner_user_id=resolved_owner_id,
        )

    def get_phase_f_cash_ledger_comparison_candidate(
        self,
        *,
        account_id: Optional[int],
        date_from: Optional[date],
        date_to: Optional[date],
        direction: Optional[str],
        page: int,
        page_size: int,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> Optional[Dict[str, Any]]:
        if not self._phase_f_enabled or self._phase_f_store is None:
            return None

        resolved_owner_id = None if include_all_owners else self.require_user_id(owner_id)
        return self._phase_f_store.query_cash_ledger_comparison_candidate(
            account_id=int(account_id) if account_id is not None else None,
            date_from=date_from,
            date_to=date_to,
            direction=direction,
            page=int(page),
            page_size=int(page_size),
            owner_user_id=resolved_owner_id,
        )

    def get_phase_f_corporate_actions_comparison_candidate(
        self,
        *,
        account_id: Optional[int],
        date_from: Optional[date],
        date_to: Optional[date],
        symbol: Optional[str],
        action_type: Optional[str],
        page: int,
        page_size: int,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> Optional[Dict[str, Any]]:
        if not self._phase_f_enabled or self._phase_f_store is None:
            return None

        resolved_owner_id = None if include_all_owners else self.require_user_id(owner_id)
        return self._phase_f_store.query_corporate_actions_comparison_candidate(
            account_id=int(account_id) if account_id is not None else None,
            date_from=date_from,
            date_to=date_to,
            symbol=symbol,
            action_type=action_type,
            page=int(page),
            page_size=int(page_size),
            owner_user_id=resolved_owner_id,
        )

    def sync_phase_g_runtime_config_shadow(
        self,
        *,
        raw_config_map: Dict[str, str],
        field_schema_by_key: Dict[str, Dict[str, Any]],
        updated_by_user_id: Optional[str] = None,
    ) -> bool:
        if not self._phase_g_enabled or self._phase_g_store is None:
            return False
        self._phase_g_store.replace_config_snapshot(
            raw_config_map=dict(raw_config_map or {}),
            field_schema_by_key=dict(field_schema_by_key or {}),
            updated_by_user_id=updated_by_user_id,
        )
        return True

    def record_phase_g_admin_action(
        self,
        *,
        action_key: str,
        actor_user_id: Optional[str],
        actor_role: Optional[str],
        subsystem: str,
        category: Optional[str],
        message: Optional[str],
        detail_json: Optional[Dict[str, Any]],
        related_session_key: Optional[str],
        destructive: bool,
        status: str,
        severity: str,
        outcome: Optional[str],
        request_json: Optional[Dict[str, Any]] = None,
        result_json: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
    ) -> Dict[str, int]:
        if not self._phase_g_enabled or self._phase_g_store is None:
            return {}

        occurred_at = created_at or datetime.now()
        admin_log_id = self._phase_g_store.append_admin_log(
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            subsystem=subsystem,
            category=category,
            event_type=action_key,
            target_type="subsystem",
            target_id=subsystem,
            severity=severity,
            outcome=outcome,
            message=message,
            detail_json=detail_json,
            related_session_key=related_session_key,
            occurred_at=occurred_at,
        )
        system_action_id = self._phase_g_store.append_system_action(
            action_key=action_key,
            actor_user_id=actor_user_id,
            destructive=destructive,
            status=status,
            request_json=request_json,
            result_json=result_json,
            admin_log_id=admin_log_id,
            created_at=occurred_at,
            completed_at=occurred_at,
        )
        return {
            "admin_log_id": int(admin_log_id),
            "system_action_id": int(system_action_id),
        }

    def list_phase_g_admin_logs(self, *, limit: int = 50) -> List[Dict[str, Any]]:
        if not self._phase_g_enabled or self._phase_g_store is None:
            return []
        return self._phase_g_store.list_admin_logs(limit=limit)

    def list_phase_g_system_actions(self, *, limit: int = 50) -> List[Dict[str, Any]]:
        if not self._phase_g_enabled or self._phase_g_store is None:
            return []
        return self._phase_g_store.list_system_actions(limit=limit)

    def list_phase_g_execution_sessions(
        self,
        *,
        limit: int = 50,
        subsystem: Optional[str] = None,
        overall_status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if not self._phase_g_enabled or self._phase_g_store is None:
            return []
        return self._phase_g_store.list_execution_sessions(
            limit=limit,
            subsystem=subsystem,
            overall_status=overall_status,
        )

    def get_phase_g_execution_session_detail(self, session_id: str) -> Optional[Dict[str, Any]]:
        if not self._phase_g_enabled or self._phase_g_store is None:
            return None
        return self._phase_g_store.get_execution_session_detail(session_id)

    def describe_phase_g_execution_log_status(
        self,
        *,
        include_connection_probe: bool = False,
    ) -> Dict[str, Any]:
        topology = self.describe_database_topology(include_connection_probe=include_connection_probe)
        return storage_phase_g_observability.build_phase_g_execution_log_status(
            self,
            topology=topology,
            include_connection_probe=include_connection_probe,
        )

    def upsert_user_notification_preferences(
        self,
        user_id: str,
        *,
        email: Optional[str],
        enabled: bool,
        channel: str = "email",
        discord_webhook: Optional[str] = None,
        discord_enabled: bool = False,
    ) -> Dict[str, Any]:
        resolved_user_id = self.require_user_id(user_id)
        normalized_channel = str(channel or "email").strip().lower() or "email"
        if normalized_channel not in {"email", "discord", "multi"}:
            raise ValueError("unsupported notification channel")

        normalized_email = str(email or "").strip() or None
        normalized_enabled = bool(enabled) and bool(normalized_email)
        normalized_discord_webhook = str(discord_webhook or "").strip() or None
        normalized_discord_enabled = bool(discord_enabled) and bool(normalized_discord_webhook)
        if normalized_enabled and normalized_discord_enabled:
            normalized_channel = "multi"
        elif normalized_discord_enabled and not normalized_enabled:
            normalized_channel = "discord"
        else:
            normalized_channel = "email"
        if self._phase_a_enabled and self._phase_a_store is not None:
            return self._phase_a_store.upsert_user_notification_preferences(
                resolved_user_id,
                email=normalized_email,
                enabled=normalized_enabled,
                channel=normalized_channel,
                discord_webhook=normalized_discord_webhook,
                discord_enabled=normalized_discord_enabled,
            )

        payload = {
            "version": 2,
            "channel": normalized_channel,
            "enabled": normalized_enabled,
            "email": normalized_email,
            "email_enabled": normalized_enabled,
            "discord_webhook": normalized_discord_webhook,
            "discord_enabled": normalized_discord_enabled,
        }

        with self.get_session() as session:
            row = session.execute(
                select(UserPreference).where(UserPreference.user_id == resolved_user_id).limit(1)
            ).scalar_one_or_none()
            if row is None:
                row = UserPreference(
                    user_id=resolved_user_id,
                    notification_preferences_json=json.dumps(payload, ensure_ascii=False),
                )
                session.add(row)
            else:
                row.notification_preferences_json = json.dumps(payload, ensure_ascii=False)
                row.updated_at = datetime.now()
            session.commit()

        return self.get_user_notification_preferences(resolved_user_id)
    
    def has_today_data(self, code: str, target_date: Optional[date] = None) -> bool:
        """
        检查是否已有指定日期的数据
        
        用于断点续传逻辑：如果已有数据则跳过网络请求
        
        Args:
            code: 股票代码
            target_date: 目标日期（默认今天）
            
        Returns:
            是否存在数据
        """
        if target_date is None:
            target_date = date.today()
        # 注意：这里的 target_date 语义是“自然日”，而不是“最新交易日”。
        # 在周末/节假日/非交易日运行时，即使数据库已有最新交易日数据，这里也会返回 False。
        # 该行为目前保留（按需求不改逻辑）。
        
        with self.get_session() as session:
            result = session.execute(
                select(StockDaily).where(
                    and_(
                        StockDaily.code == code,
                        StockDaily.date == target_date
                    )
                )
            ).scalar_one_or_none()
            
            return result is not None
    
    def get_latest_data(
        self, 
        code: str, 
        days: int = 2
    ) -> List[StockDaily]:
        """
        获取最近 N 天的数据
        
        用于计算"相比昨日"的变化
        
        Args:
            code: 股票代码
            days: 获取天数
            
        Returns:
            StockDaily 对象列表（按日期降序）
        """
        with self.get_session() as session:
            results = session.execute(
                select(StockDaily)
                .where(StockDaily.code == code)
                .order_by(desc(StockDaily.date))
                .limit(days)
            ).scalars().all()
            
            return list(results)

    def save_news_intel(
        self,
        code: str,
        name: str,
        dimension: str,
        query: str,
        response: 'SearchResponse',
        query_context: Optional[Dict[str, str]] = None
    ) -> int:
        """
        保存新闻情报到数据库

        去重策略：
        - 优先按 URL 去重（唯一约束）
        - URL 缺失时按 title + source + published_date 进行软去重

        关联策略：
        - query_context 记录用户查询信息（平台、用户、会话、原始指令等）
        """
        if not response or not response.results:
            return 0

        saved_count = 0
        query_ctx = query_context or {}
        current_query_id = (query_ctx.get("query_id") or "").strip()

        with self.get_session() as session:
            try:
                for item in response.results:
                    title = (item.title or '').strip()
                    url = (item.url or '').strip()
                    source = (item.source or '').strip()
                    snippet = (item.snippet or '').strip()
                    published_date = self._parse_published_date(item.published_date)

                    if not title and not url:
                        continue

                    url_key = url or self._build_fallback_url_key(
                        code=code,
                        title=title,
                        source=source,
                        published_date=published_date
                    )

                    # 优先按 URL 或兜底键去重
                    existing = session.execute(
                        select(NewsIntel).where(NewsIntel.url == url_key)
                    ).scalar_one_or_none()

                    if existing:
                        existing.name = name or existing.name
                        existing.dimension = dimension or existing.dimension
                        existing.query = query or existing.query
                        existing.provider = response.provider or existing.provider
                        existing.snippet = snippet or existing.snippet
                        existing.source = source or existing.source
                        existing.published_date = published_date or existing.published_date
                        existing.fetched_at = datetime.now()

                        if query_context:
                            # Keep the first query_id to avoid overwriting historical links.
                            if not existing.query_id and current_query_id:
                                existing.query_id = current_query_id
                            existing.query_source = (
                                query_context.get("query_source") or existing.query_source
                            )
                            existing.requester_platform = (
                                query_context.get("requester_platform") or existing.requester_platform
                            )
                            existing.requester_user_id = (
                                query_context.get("requester_user_id") or existing.requester_user_id
                            )
                            existing.requester_user_name = (
                                query_context.get("requester_user_name") or existing.requester_user_name
                            )
                            existing.requester_chat_id = (
                                query_context.get("requester_chat_id") or existing.requester_chat_id
                            )
                            existing.requester_message_id = (
                                query_context.get("requester_message_id") or existing.requester_message_id
                            )
                            existing.requester_query = (
                                query_context.get("requester_query") or existing.requester_query
                            )
                    else:
                        try:
                            with session.begin_nested():
                                record = NewsIntel(
                                    code=code,
                                    name=name,
                                    dimension=dimension,
                                    query=query,
                                    provider=response.provider,
                                    title=title,
                                    snippet=snippet,
                                    url=url_key,
                                    source=source,
                                    published_date=published_date,
                                    fetched_at=datetime.now(),
                                    query_id=current_query_id or None,
                                    query_source=query_ctx.get("query_source"),
                                    requester_platform=query_ctx.get("requester_platform"),
                                    requester_user_id=query_ctx.get("requester_user_id"),
                                    requester_user_name=query_ctx.get("requester_user_name"),
                                    requester_chat_id=query_ctx.get("requester_chat_id"),
                                    requester_message_id=query_ctx.get("requester_message_id"),
                                    requester_query=query_ctx.get("requester_query"),
                                )
                                session.add(record)
                                session.flush()
                            saved_count += 1
                        except IntegrityError:
                            # 单条 URL 唯一约束冲突（如并发插入），仅跳过本条，保留本批其余成功项
                            logger.debug("新闻情报重复（已跳过）: %s %s", code, url_key)

                session.commit()
                logger.info(f"保存新闻情报成功: {code}, 新增 {saved_count} 条")

            except Exception as e:
                session.rollback()
                logger.error(f"保存新闻情报失败: {e}")
                raise

        return saved_count

    def save_fundamental_snapshot(
        self,
        query_id: str,
        code: str,
        payload: Optional[Dict[str, Any]],
        source_chain: Optional[Any] = None,
        coverage: Optional[Any] = None,
    ) -> int:
        """
        保存基本面快照（P0 write-only）。失败不抛异常，返回写入条数 0/1。
        """
        if not query_id or not code or payload is None:
            return 0

        with self.get_session() as session:
            try:
                session.add(
                    FundamentalSnapshot(
                        query_id=query_id,
                        code=code,
                        payload=self._safe_json_dumps(payload),
                        source_chain=self._safe_json_dumps(source_chain or []),
                        coverage=self._safe_json_dumps(coverage or {}),
                    )
                )
                session.commit()
                return 1
            except Exception as e:
                session.rollback()
                logger.debug(
                    "基本面快照写入失败（fail-open）: query_id=%s code=%s err=%s",
                    query_id,
                    code,
                    e,
                )
                return 0

    def get_latest_fundamental_snapshot(
        self,
        query_id: str,
        code: str,
    ) -> Optional[Dict[str, Any]]:
        """
        获取指定 query_id + code 的最新基本面快照 payload。

        读取失败或不存在时返回 None（fail-open）。
        """
        if not query_id or not code:
            return None

        with self.get_session() as session:
            try:
                row = session.execute(
                    select(FundamentalSnapshot)
                    .where(
                        and_(
                            FundamentalSnapshot.query_id == query_id,
                            FundamentalSnapshot.code == code,
                        )
                    )
                    .order_by(desc(FundamentalSnapshot.created_at))
                    .limit(1)
                ).scalar_one_or_none()
            except Exception as e:
                logger.debug(
                    "基本面快照读取失败（fail-open）: query_id=%s code=%s err=%s",
                    query_id,
                    code,
                    e,
                )
                return None

            if row is None:
                return None
            try:
                payload = json.loads(row.payload or "{}")
                return payload if isinstance(payload, dict) else None
            except Exception:
                return None

    def get_recent_news(self, code: str, days: int = 7, limit: int = 20) -> List[NewsIntel]:
        """
        获取指定股票最近 N 天的新闻情报
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        with self.get_session() as session:
            results = session.execute(
                select(NewsIntel)
                .where(
                    and_(
                        NewsIntel.code == code,
                        NewsIntel.fetched_at >= cutoff_date
                    )
                )
                .order_by(desc(NewsIntel.fetched_at))
                .limit(limit)
            ).scalars().all()

            return list(results)

    def get_news_intel_by_query_id(self, query_id: str, limit: int = 20) -> List[NewsIntel]:
        """
        根据 query_id 获取新闻情报列表

        Args:
            query_id: 分析记录唯一标识
            limit: 返回数量限制

        Returns:
            NewsIntel 列表（按发布时间或抓取时间倒序）
        """
        from sqlalchemy import func

        with self.get_session() as session:
            results = session.execute(
                select(NewsIntel)
                .where(NewsIntel.query_id == query_id)
                .order_by(
                    desc(func.coalesce(NewsIntel.published_date, NewsIntel.fetched_at)),
                    desc(NewsIntel.fetched_at)
                )
                .limit(limit)
            ).scalars().all()

            return list(results)

    def save_analysis_history(
        self,
        result: Any,
        query_id: str,
        report_type: str,
        news_content: Optional[str],
        context_snapshot: Optional[Dict[str, Any]] = None,
        save_snapshot: bool = True,
        owner_id: Optional[str] = None,
        is_test: bool = False,
    ) -> int:
        """
        保存分析结果历史记录
        """
        if result is None:
            return 0

        sniper_points = self._extract_sniper_points(result)
        raw_result = self._build_raw_result(result)
        context_text = None
        if save_snapshot and context_snapshot is not None:
            context_text = self._safe_json_dumps(context_snapshot)
        resolved_owner_id = self.require_user_id(owner_id)

        record = AnalysisHistory(
            owner_id=resolved_owner_id,
            query_id=query_id,
            code=result.code,
            name=result.name,
            report_type=report_type,
            sentiment_score=result.sentiment_score,
            operation_advice=result.operation_advice,
            trend_prediction=result.trend_prediction,
            analysis_summary=result.analysis_summary,
            raw_result=self._safe_json_dumps(raw_result),
            news_content=news_content,
            context_snapshot=context_text,
            ideal_buy=sniper_points.get("ideal_buy"),
            secondary_buy=sniper_points.get("secondary_buy"),
            stop_loss=sniper_points.get("stop_loss"),
            take_profit=sniper_points.get("take_profit"),
            is_test=bool(is_test),
            created_at=datetime.now(),
        )

        with self.get_session() as session:
            try:
                session.add(record)
                session.flush()
                if self._phase_b_enabled and self._phase_b_store is not None:
                    self._phase_b_store.upsert_analysis_history_shadow(
                        legacy_analysis_history_id=int(record.id),
                        owner_user_id=resolved_owner_id,
                        query_id=query_id,
                        canonical_symbol=str(result.code or ""),
                        display_name=getattr(result, "name", None),
                        report_type=report_type,
                        sentiment_score=getattr(result, "sentiment_score", None),
                        operation_advice=getattr(result, "operation_advice", None),
                        trend_prediction=getattr(result, "trend_prediction", None),
                        summary_text=getattr(result, "analysis_summary", None),
                        raw_result=record.raw_result,
                        news_content=news_content,
                        context_snapshot=context_text,
                        created_at=record.created_at,
                    )
                session.commit()
                return 1
            except Exception as e:
                session.rollback()
                logger.error(f"保存分析历史失败: {e}")
                return 0

    def attach_analysis_report_payload(
        self,
        *,
        query_id: str,
        report_payload: Dict[str, Any],
        owner_id: Optional[str] = None,
    ) -> int:
        """Attach the canonical persisted report payload onto the latest matching history row."""
        if not query_id or not isinstance(report_payload, dict):
            return 0

        resolved_owner_id = self.require_user_id(owner_id)
        with self.get_session() as session:
            try:
                record = (
                    session.query(AnalysisHistory)
                    .filter(
                        AnalysisHistory.query_id == query_id,
                        AnalysisHistory.owner_id == resolved_owner_id,
                    )
                    .order_by(AnalysisHistory.id.desc())
                    .first()
                )
                if record is None:
                    return 0

                try:
                    raw_result = json.loads(record.raw_result) if record.raw_result else {}
                except (TypeError, ValueError, json.JSONDecodeError):
                    raw_result = {}
                if not isinstance(raw_result, dict):
                    raw_result = {}

                payload = dict(report_payload)
                meta = dict(payload.get("meta") or {})
                summary = dict(payload.get("summary") or {})
                details = dict(payload.get("details") or {})
                generated_at = to_beijing_iso8601(
                    meta.get("generated_at")
                    or meta.get("report_generated_at")
                    or record.created_at
                )
                meta["id"] = int(record.id)
                if generated_at:
                    meta["generated_at"] = generated_at
                    meta.setdefault("report_generated_at", generated_at)
                company_name = str(
                    meta.get("company_name")
                    or meta.get("stock_name")
                    or record.name
                    or record.code
                ).strip()
                meta["company_name"] = company_name
                meta.setdefault("stock_name", company_name)
                resolved_is_test = bool(meta.get("is_test") or record.is_test)
                meta["is_test"] = resolved_is_test
                if summary.get("analysis_summary") and not summary.get("strategy_summary"):
                    summary["strategy_summary"] = summary.get("analysis_summary")
                if meta.get("strategy_type") is None:
                    meta["strategy_type"] = meta.get("report_type") or record.report_type
                payload["meta"] = meta
                payload["summary"] = summary
                payload["details"] = details

                raw_result["persisted_report"] = payload

                standard_report = details.get("standard_report")
                if isinstance(standard_report, dict):
                    raw_result["standard_report"] = standard_report

                report_language = meta.get("report_language")
                if report_language:
                    raw_result["report_language"] = report_language

                model_used = meta.get("model_used")
                if model_used:
                    raw_result["model_used"] = model_used

                record.raw_result = self._safe_json_dumps(raw_result)
                record.is_test = resolved_is_test
                session.commit()
                return 1
            except Exception as e:
                session.rollback()
                logger.error(f"附加持久化报告失败: {e}")
                return 0

    def get_analysis_history(
        self,
        code: Optional[str] = None,
        query_id: Optional[str] = None,
        days: int = 30,
        limit: int = 50,
        exclude_query_id: Optional[str] = None,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> List[AnalysisHistory]:
        """
        Query analysis history records.

        Notes:
        - If query_id is provided, perform exact lookup and ignore days window.
        - If query_id is not provided, apply days-based time filtering.
        - exclude_query_id: exclude records with this query_id (for history comparison).
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        with self.get_session() as session:
            conditions = []
            if not include_all_owners:
                conditions.append(AnalysisHistory.owner_id == self.require_user_id(owner_id))

            if query_id:
                conditions.append(AnalysisHistory.query_id == query_id)
            else:
                conditions.append(AnalysisHistory.created_at >= cutoff_date)

            if code:
                conditions.append(AnalysisHistory.code == code)

            # exclude_query_id only applies when not doing exact lookup (query_id is None)
            if exclude_query_id and not query_id:
                conditions.append(AnalysisHistory.query_id != exclude_query_id)

            results = session.execute(
                select(AnalysisHistory)
                .where(and_(*conditions))
                .order_by(desc(AnalysisHistory.created_at))
                .limit(limit)
            ).scalars().all()

            return list(results)
    
    def get_analysis_history_paginated(
        self,
        code: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        offset: int = 0,
        limit: int = 20,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
        include_test: bool = True,
    ) -> Tuple[List[AnalysisHistory], int]:
        """
        分页查询分析历史记录（带总数）
        
        Args:
            code: 股票代码筛选
            start_date: 开始日期（含）
            end_date: 结束日期（含）
            offset: 偏移量（跳过前 N 条）
            limit: 每页数量
            
        Returns:
            Tuple[List[AnalysisHistory], int]: (记录列表, 总数)
        """
        from sqlalchemy import func
        
        with self.get_session() as session:
            conditions = []
            if not include_all_owners:
                conditions.append(AnalysisHistory.owner_id == self.require_user_id(owner_id))
            
            if code:
                conditions.append(AnalysisHistory.code == code)
            if start_date:
                # created_at >= start_date 00:00:00
                conditions.append(AnalysisHistory.created_at >= datetime.combine(start_date, datetime.min.time()))
            if end_date:
                # created_at < end_date+1 00:00:00 (即 <= end_date 23:59:59)
                conditions.append(AnalysisHistory.created_at < datetime.combine(end_date + timedelta(days=1), datetime.min.time()))
            if not include_test:
                conditions.append(AnalysisHistory.is_test.is_(False))
            
            # 构建 where 子句
            where_clause = and_(*conditions) if conditions else True
            
            # 查询总数
            total_query = select(func.count(AnalysisHistory.id)).where(where_clause)
            total = session.execute(total_query).scalar() or 0
            
            # 查询分页数据
            data_query = (
                select(AnalysisHistory)
                .where(where_clause)
                .order_by(desc(AnalysisHistory.created_at))
                .offset(offset)
                .limit(limit)
            )
            results = session.execute(data_query).scalars().all()
            
            return list(results), total
    
    def get_analysis_history_by_id(
        self,
        record_id: int,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> Optional[AnalysisHistory]:
        """
        根据数据库主键 ID 查询单条分析历史记录
        
        由于 query_id 可能重复（批量分析时多条记录共享同一 query_id），
        使用主键 ID 确保精确查询唯一记录。
        
        Args:
            record_id: 分析历史记录的主键 ID
            
        Returns:
            AnalysisHistory 对象，不存在返回 None
        """
        with self.get_session() as session:
            conditions = [AnalysisHistory.id == record_id]
            if not include_all_owners:
                conditions.append(AnalysisHistory.owner_id == self.require_user_id(owner_id))
            result = session.execute(
                select(AnalysisHistory).where(and_(*conditions))
            ).scalars().first()
            return result

    def list_recent_analysis_symbols(
        self,
        *,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
        limit: Optional[int] = DEFAULT_RECENT_ANALYSIS_SYMBOL_LIMIT,
    ) -> List[Tuple[str, Optional[str]]]:
        """Return latest distinct analysis-history codes and names in newest-first order."""
        resolved_limit = self._resolve_bounded_limit(
            limit,
            default=DEFAULT_RECENT_ANALYSIS_SYMBOL_LIMIT,
            high=MAX_RECENT_ANALYSIS_SYMBOL_LIMIT,
        )
        normalized_owner_id = str(owner_id or "").strip()
        code_expr = func.trim(AnalysisHistory.code)

        with self.get_session() as session:
            conditions = [
                AnalysisHistory.code.isnot(None),
                code_expr != "",
            ]
            if normalized_owner_id and not include_all_owners:
                conditions.append(AnalysisHistory.owner_id == self.require_user_id(normalized_owner_id))

            ranked_symbols = (
                select(
                    code_expr.label("code"),
                    AnalysisHistory.name.label("name"),
                    AnalysisHistory.created_at.label("created_at"),
                    AnalysisHistory.id.label("id"),
                    func.row_number()
                    .over(
                        partition_by=code_expr,
                        order_by=(AnalysisHistory.created_at.desc(), AnalysisHistory.id.desc()),
                    )
                    .label("symbol_rank"),
                )
                .where(and_(*conditions))
                .subquery()
            )
            rows = session.execute(
                select(ranked_symbols.c.code, ranked_symbols.c.name)
                .where(ranked_symbols.c.symbol_rank == 1)
                .order_by(ranked_symbols.c.created_at.desc(), ranked_symbols.c.id.desc())
                .limit(resolved_limit)
            ).all()
        return [
            (str(code), str(name) if name is not None else None)
            for code, name in rows
            if code
        ]

    def delete_analysis_history_records(
        self,
        record_ids: List[int],
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> int:
        """
        删除指定的分析历史记录。

        同时清理依赖这些历史记录的回测结果，避免外键约束失败。

        Args:
            record_ids: 要删除的历史记录主键 ID 列表

        Returns:
            实际删除的历史记录数量
        """
        ids = sorted({int(record_id) for record_id in record_ids if record_id is not None})
        if not ids:
            return 0

        with self.session_scope() as session:
            owner_filter = []
            if not include_all_owners:
                owner_filter.append(AnalysisHistory.owner_id == self.require_user_id(owner_id))
            matching_analysis_ids = session.execute(
                select(AnalysisHistory.id).where(
                    and_(AnalysisHistory.id.in_(ids), *owner_filter) if owner_filter else AnalysisHistory.id.in_(ids)
                )
            ).scalars().all()
            if not matching_analysis_ids:
                return 0
            if self._phase_b_enabled and self._phase_b_store is not None:
                self._phase_b_store.delete_analysis_history_shadow(matching_analysis_ids)
            session.execute(
                delete(BacktestResult).where(BacktestResult.analysis_history_id.in_(matching_analysis_ids))
            )
            result = session.execute(
                delete(AnalysisHistory).where(AnalysisHistory.id.in_(matching_analysis_ids))
            )
            return result.rowcount or 0

    def delete_all_analysis_history_records(
        self,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> int:
        """
        删除当前 owner 范围内的全部分析历史记录。

        同时清理依赖这些历史记录的回测结果，避免残留孤儿数据。
        """
        with self.session_scope() as session:
            owner_filter = []
            if not include_all_owners:
                owner_filter.append(AnalysisHistory.owner_id == self.require_user_id(owner_id))

            matching_analysis_ids = session.execute(
                select(AnalysisHistory.id).where(and_(*owner_filter)) if owner_filter else select(AnalysisHistory.id)
            ).scalars().all()
            if not matching_analysis_ids:
                return 0

            if self._phase_b_enabled and self._phase_b_store is not None:
                self._phase_b_store.delete_analysis_history_shadow(matching_analysis_ids)

            session.execute(
                delete(BacktestResult).where(BacktestResult.analysis_history_id.in_(matching_analysis_ids))
            )
            result = session.execute(
                delete(AnalysisHistory).where(AnalysisHistory.id.in_(matching_analysis_ids))
            )
            return result.rowcount or 0

    def get_latest_analysis_by_query_id(
        self,
        query_id: str,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> Optional[AnalysisHistory]:
        """
        根据 query_id 查询最新一条分析历史记录

        query_id 在批量分析时可能重复，故返回最近创建的一条。

        Args:
            query_id: 分析记录关联的 query_id

        Returns:
            AnalysisHistory 对象，不存在返回 None
        """
        with self.get_session() as session:
            conditions = [AnalysisHistory.query_id == query_id]
            if not include_all_owners:
                conditions.append(AnalysisHistory.owner_id == self.require_user_id(owner_id))
            result = session.execute(
                select(AnalysisHistory)
                .where(and_(*conditions))
                .order_by(desc(AnalysisHistory.created_at))
                .limit(1)
            ).scalars().first()
            return result

    def create_execution_log_session(
        self,
        *,
        session_id: str,
        task_id: Optional[str] = None,
        query_id: Optional[str] = None,
        code: Optional[str] = None,
        name: Optional[str] = None,
        overall_status: str = "running",
        truth_level: str = "mixed",
        summary: Optional[Dict[str, Any]] = None,
        started_at: Optional[datetime] = None,
    ) -> None:
        """Create or update an execution log session."""
        if not session_id:
            return
        now = datetime.now()
        safe_summary = sanitize_metadata(summary or {})
        with self.session_scope() as session:
            row = session.execute(
                select(ExecutionLogSession).where(ExecutionLogSession.session_id == session_id)
            ).scalars().first()
            if row is None:
                row = ExecutionLogSession(
                    session_id=session_id,
                    task_id=task_id,
                    query_id=query_id,
                    code=code,
                    name=name,
                    overall_status=overall_status,
                    truth_level=truth_level,
                    summary_json=self._safe_json_dumps(safe_summary),
                    started_at=started_at or now,
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
            else:
                row.task_id = task_id or row.task_id
                row.query_id = query_id or row.query_id
                row.code = code or row.code
                row.name = name or row.name
                row.overall_status = overall_status or row.overall_status
                row.truth_level = truth_level or row.truth_level
                if summary is not None:
                    row.summary_json = self._safe_json_dumps(safe_summary)
                if started_at is not None:
                    row.started_at = started_at
                row.updated_at = now

        if self._phase_g_enabled and self._phase_g_store is not None:
            try:
                self._phase_g_store.upsert_execution_session(
                    session_id=session_id,
                    task_id=task_id,
                    query_id=query_id,
                    canonical_symbol=code,
                    display_name=name,
                    overall_status=overall_status,
                    truth_level=truth_level,
                    summary_json=safe_summary,
                    started_at=started_at or now,
                )
            except Exception as exc:
                logger.warning("Phase G execution session shadow sync failed during create: %s", exc)

    def append_execution_log_event(
        self,
        *,
        session_id: str,
        phase: str,
        status: str,
        step: Optional[str] = None,
        target: Optional[str] = None,
        truth_level: str = "inferred",
        message: Optional[str] = None,
        error_code: Optional[str] = None,
        detail: Optional[Dict[str, Any]] = None,
        event_at: Optional[datetime] = None,
    ) -> None:
        """Append a structured event into execution logs."""
        if not session_id or not phase:
            return
        safe_message = sanitize_message(str(message)) if message is not None else None
        safe_detail = sanitize_metadata(detail or {})
        row = ExecutionLogEvent(
            session_id=session_id,
            event_at=event_at or datetime.now(),
            phase=str(phase).strip(),
            step=str(step).strip() if step else None,
            target=str(target).strip() if target else None,
            status=str(status or "unknown").strip(),
            truth_level=str(truth_level or "inferred").strip(),
            message=(str(safe_message).strip() or None) if safe_message is not None else None,
            error_code=(str(error_code).strip() or None) if error_code is not None else None,
            detail_json=self._safe_json_dumps(safe_detail),
        )
        with self.session_scope() as session:
            session.add(row)

        self._emit_execution_log_notification(
            session_id=session_id,
            phase=phase,
            status=status,
            step=step,
            message=safe_message,
            detail=safe_detail,
        )

        if self._phase_g_enabled and self._phase_g_store is not None:
            try:
                self._phase_g_store.append_execution_event(
                    session_id=session_id,
                    phase=phase,
                    step=step,
                    target=target,
                    status=status,
                    truth_level=truth_level,
                    message=safe_message,
                    error_code=error_code,
                    detail_json=safe_detail,
                    occurred_at=event_at,
                )
            except Exception as exc:
                logger.warning("Phase G execution event shadow sync failed during append: %s", exc)

    def _emit_execution_log_notification(
        self,
        *,
        session_id: str,
        phase: str,
        status: str,
        step: Optional[str],
        message: Optional[str],
        detail: Dict[str, Any],
    ) -> None:
        try:
            log_detail = detail.get("log") if isinstance(detail, dict) and isinstance(detail.get("log"), dict) else {}
            log_level = str(log_detail.get("level") or _execution_log_level_from_status(status)).strip().upper()
            if log_level not in {"NOTICE", "WARNING", "ERROR", "CRITICAL"}:
                return
            service_factory = AdminNotificationService
            if service_factory is None:
                from src.services.notification_service import NotificationService as service_factory

            service_factory().emit_log_event(
                log_level=log_level,
                category=str(log_detail.get("category") or phase or "system").strip() or "system",
                event_name=str(step or log_detail.get("event_name") or status or "ExecutionLogEvent").strip(),
                message=str(message or "").strip(),
                session_id=session_id,
                payload={"status": status},
            )
        except Exception as exc:
            logger.warning("execution log notification emit failed: %s", exc)

    def finalize_execution_log_session(
        self,
        *,
        session_id: str,
        overall_status: str,
        truth_level: str = "mixed",
        query_id: Optional[str] = None,
        analysis_history_id: Optional[int] = None,
        summary: Optional[Dict[str, Any]] = None,
        ended_at: Optional[datetime] = None,
    ) -> None:
        """Finalize a session status and enrich linkage fields."""
        if not session_id:
            return
        now = datetime.now()
        safe_summary = sanitize_metadata(summary or {}) if summary is not None else None
        with self.session_scope() as session:
            row = session.execute(
                select(ExecutionLogSession).where(ExecutionLogSession.session_id == session_id)
            ).scalars().first()
            if row is None:
                return
            row.overall_status = str(overall_status or row.overall_status).strip()
            row.truth_level = str(truth_level or row.truth_level).strip()
            if query_id:
                row.query_id = query_id
            if analysis_history_id is not None:
                row.analysis_history_id = int(analysis_history_id)
            if summary is not None:
                row.summary_json = self._safe_json_dumps(safe_summary)
            row.ended_at = ended_at or now
            row.updated_at = now

        if self._phase_g_enabled and self._phase_g_store is not None:
            try:
                self._phase_g_store.upsert_execution_session(
                    session_id=session_id,
                    query_id=query_id,
                    overall_status=overall_status,
                    truth_level=truth_level,
                    summary_json=safe_summary if isinstance(safe_summary, dict) else None,
                    ended_at=ended_at or now,
                )
            except Exception as exc:
                logger.warning("Phase G execution session shadow sync failed during finalize: %s", exc)

    def attach_execution_session_to_query(
        self,
        *,
        session_id: str,
        query_id: Optional[str],
    ) -> None:
        """Attach query_id/history_id linkage once history is persisted."""
        if not session_id:
            return
        with self.session_scope() as session:
            row = session.execute(
                select(ExecutionLogSession).where(ExecutionLogSession.session_id == session_id)
            ).scalars().first()
            if row is None:
                return
            if query_id:
                row.query_id = query_id
                latest = session.execute(
                    select(AnalysisHistory)
                    .where(AnalysisHistory.query_id == query_id)
                    .order_by(desc(AnalysisHistory.created_at))
                    .limit(1)
                ).scalars().first()
                if latest is not None:
                    row.analysis_history_id = latest.id
            row.updated_at = datetime.now()

        if self._phase_g_enabled and self._phase_g_store is not None and query_id:
            try:
                self._phase_g_store.upsert_execution_session(
                    session_id=session_id,
                    query_id=query_id,
                )
            except Exception as exc:
                logger.warning("Phase G execution session shadow sync failed during query attach: %s", exc)

    def list_execution_log_sessions(
        self,
        *,
        task_id: Optional[str] = None,
        stock_code: Optional[str] = None,
        status: Optional[str] = None,
        category: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        channel: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """List execution sessions with optional event-level filtering."""
        with self.get_session() as session:
            session_filters = []
            if task_id:
                session_filters.append(ExecutionLogSession.task_id == task_id)
            if stock_code:
                session_filters.append(ExecutionLogSession.code == stock_code)
            if status:
                session_filters.append(ExecutionLogSession.overall_status == status)
            if date_from:
                session_filters.append(ExecutionLogSession.started_at >= date_from)
            if date_to:
                session_filters.append(ExecutionLogSession.started_at <= date_to)

            event_filters = []
            if category:
                event_filters.append(ExecutionLogEvent.phase == category)
            if provider:
                event_filters.append(ExecutionLogEvent.target.ilike(f"%{provider}%"))
            if model:
                event_filters.append(
                    and_(
                        ExecutionLogEvent.phase.in_(["ai", "ai_model"]),
                        ExecutionLogEvent.target.ilike(f"%{model}%"),
                    )
                )
            if channel:
                event_filters.append(and_(ExecutionLogEvent.phase == "notification", ExecutionLogEvent.target.ilike(f"%{channel}%")))

            where_clause = and_(*session_filters) if session_filters else True
            if event_filters:
                event_where = and_(*event_filters)
                matched_session_ids = session.execute(
                    select(ExecutionLogEvent.session_id).where(event_where).distinct()
                ).scalars().all()
                if not matched_session_ids:
                    return [], 0
                where_clause = and_(where_clause, ExecutionLogSession.session_id.in_(matched_session_ids))

            total = session.execute(
                select(func.count(ExecutionLogSession.id)).where(where_clause)
            ).scalar() or 0

            rows = session.execute(
                select(ExecutionLogSession)
                .where(where_clause)
                .order_by(desc(ExecutionLogSession.started_at))
                .offset(max(0, int(offset)))
                .limit(max(1, min(int(limit), 200)))
            ).scalars().all()

            items: List[Dict[str, Any]] = []
            for row in rows:
                summary = {}
                try:
                    summary = json.loads(row.summary_json or "{}")
                except Exception:
                    summary = {}
                items.append(
                    {
                        "session_id": row.session_id,
                        "task_id": row.task_id,
                        "query_id": row.query_id,
                        "analysis_history_id": row.analysis_history_id,
                        "code": row.code,
                        "name": row.name,
                        "overall_status": row.overall_status,
                        "truth_level": row.truth_level,
                        "started_at": row.started_at.isoformat() if row.started_at else None,
                        "ended_at": row.ended_at.isoformat() if row.ended_at else None,
                        "summary": summary if isinstance(summary, dict) else {},
                    }
                )
            return items, int(total)

    def list_execution_log_session_details(self, session_ids: Iterable[str]) -> Dict[str, Dict[str, Any]]:
        """Return execution sessions and event timelines for a bounded id set."""
        ordered_ids: List[str] = []
        seen: set[str] = set()
        for raw_id in session_ids:
            session_id = str(raw_id or "").strip()
            if not session_id or session_id in seen:
                continue
            ordered_ids.append(session_id)
            seen.add(session_id)
            if len(ordered_ids) >= 200:
                break
        if not ordered_ids:
            return {}

        with self.get_session() as session:
            rows = session.execute(
                select(ExecutionLogSession).where(ExecutionLogSession.session_id.in_(ordered_ids))
            ).scalars().all()
            row_map = {row.session_id: row for row in rows}

            event_rows = session.execute(
                select(ExecutionLogEvent)
                .where(ExecutionLogEvent.session_id.in_(ordered_ids))
                .order_by(asc(ExecutionLogEvent.event_at), asc(ExecutionLogEvent.id))
            ).scalars().all()
            events_by_session: Dict[str, List[Dict[str, Any]]] = {session_id: [] for session_id in ordered_ids}
            for event in event_rows:
                detail = {}
                try:
                    detail = json.loads(event.detail_json or "{}")
                except Exception:
                    detail = {}
                events_by_session.setdefault(event.session_id, []).append(
                    {
                        "id": event.id,
                        "event_at": event.event_at.isoformat() if event.event_at else None,
                        "phase": event.phase,
                        "step": event.step,
                        "target": event.target,
                        "status": event.status,
                        "truth_level": event.truth_level,
                        "message": event.message,
                        "error_code": event.error_code,
                        "detail": detail if isinstance(detail, dict) else {},
                    }
                )

            details: Dict[str, Dict[str, Any]] = {}
            for session_id in ordered_ids:
                row = row_map.get(session_id)
                if row is None:
                    continue
                summary = {}
                try:
                    summary = json.loads(row.summary_json or "{}")
                except Exception:
                    summary = {}
                details[session_id] = {
                    "session_id": row.session_id,
                    "task_id": row.task_id,
                    "query_id": row.query_id,
                    "analysis_history_id": row.analysis_history_id,
                    "code": row.code,
                    "name": row.name,
                    "overall_status": row.overall_status,
                    "truth_level": row.truth_level,
                    "started_at": row.started_at.isoformat() if row.started_at else None,
                    "ended_at": row.ended_at.isoformat() if row.ended_at else None,
                    "summary": summary if isinstance(summary, dict) else {},
                    "events": events_by_session.get(session_id, []),
                }
            return details

    def get_execution_log_session_detail(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Return one execution session with its event timeline."""
        if not session_id:
            return None
        with self.get_session() as session:
            row = session.execute(
                select(ExecutionLogSession).where(ExecutionLogSession.session_id == session_id)
            ).scalars().first()
            if row is None:
                return None

            event_rows = session.execute(
                select(ExecutionLogEvent)
                .where(ExecutionLogEvent.session_id == session_id)
                .order_by(asc(ExecutionLogEvent.event_at), asc(ExecutionLogEvent.id))
            ).scalars().all()
            events: List[Dict[str, Any]] = []
            for event in event_rows:
                detail = {}
                try:
                    detail = json.loads(event.detail_json or "{}")
                except Exception:
                    detail = {}
                events.append(
                    {
                        "id": event.id,
                        "event_at": event.event_at.isoformat() if event.event_at else None,
                        "phase": event.phase,
                        "step": event.step,
                        "target": event.target,
                        "status": event.status,
                        "truth_level": event.truth_level,
                        "message": event.message,
                        "error_code": event.error_code,
                        "detail": detail if isinstance(detail, dict) else {},
                    }
                )

            summary = {}
            try:
                summary = json.loads(row.summary_json or "{}")
            except Exception:
                summary = {}

            return {
                "session_id": row.session_id,
                "task_id": row.task_id,
                "query_id": row.query_id,
                "analysis_history_id": row.analysis_history_id,
                "code": row.code,
                "name": row.name,
                "overall_status": row.overall_status,
                "truth_level": row.truth_level,
                "started_at": row.started_at.isoformat() if row.started_at else None,
                "ended_at": row.ended_at.isoformat() if row.ended_at else None,
                "summary": summary if isinstance(summary, dict) else {},
                "events": events,
            }
    
    def get_data_range(
        self, 
        code: str, 
        start_date: date, 
        end_date: date
    ) -> List[StockDaily]:
        """
        获取指定日期范围的数据
        
        Args:
            code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            StockDaily 对象列表
        """
        with self.get_session() as session:
            results = session.execute(
                select(StockDaily)
                .where(
                    and_(
                        StockDaily.code == code,
                        StockDaily.date >= start_date,
                        StockDaily.date <= end_date
                    )
                )
                .order_by(StockDaily.date)
            ).scalars().all()
            
            return list(results)
    
    def save_daily_data(
        self, 
        df: pd.DataFrame, 
        code: str,
        data_source: str = "Unknown"
    ) -> int:
        """
        保存日线数据到数据库
        
        策略：
        - 使用 UPSERT 逻辑（存在则更新，不存在则插入）
        - 跳过已存在的数据，避免重复
        
        Args:
            df: 包含日线数据的 DataFrame
            code: 股票代码
            data_source: 数据来源名称
            
        Returns:
            新增/更新的记录数
        """
        if df is None or df.empty:
            logger.warning(f"保存数据为空，跳过 {code}")
            return 0
        
        saved_count = 0
        
        with self.get_session() as session:
            try:
                for _, row in df.iterrows():
                    # 解析日期
                    row_date = row.get('date')
                    if isinstance(row_date, str):
                        row_date = datetime.strptime(row_date, '%Y-%m-%d').date()
                    elif isinstance(row_date, datetime):
                        row_date = row_date.date()
                    elif isinstance(row_date, pd.Timestamp):
                        row_date = row_date.date()
                    
                    # 检查是否已存在
                    existing = session.execute(
                        select(StockDaily).where(
                            and_(
                                StockDaily.code == code,
                                StockDaily.date == row_date
                            )
                        )
                    ).scalar_one_or_none()
                    
                    if existing:
                        # 更新现有记录
                        existing.open = row.get('open')
                        existing.high = row.get('high')
                        existing.low = row.get('low')
                        existing.close = row.get('close')
                        existing.volume = row.get('volume')
                        existing.amount = row.get('amount')
                        existing.pct_chg = row.get('pct_chg')
                        existing.ma5 = row.get('ma5')
                        existing.ma10 = row.get('ma10')
                        existing.ma20 = row.get('ma20')
                        existing.volume_ratio = row.get('volume_ratio')
                        existing.data_source = data_source
                        existing.updated_at = datetime.now()
                    else:
                        # 创建新记录
                        record = StockDaily(
                            code=code,
                            date=row_date,
                            open=row.get('open'),
                            high=row.get('high'),
                            low=row.get('low'),
                            close=row.get('close'),
                            volume=row.get('volume'),
                            amount=row.get('amount'),
                            pct_chg=row.get('pct_chg'),
                            ma5=row.get('ma5'),
                            ma10=row.get('ma10'),
                            ma20=row.get('ma20'),
                            volume_ratio=row.get('volume_ratio'),
                            data_source=data_source,
                        )
                        session.add(record)
                        saved_count += 1
                
                session.commit()
                logger.info(f"保存 {code} 数据成功，新增 {saved_count} 条")
                
            except Exception as e:
                session.rollback()
                logger.error(f"保存 {code} 数据失败: {e}")
                raise
        
        return saved_count
    
    def get_analysis_context(
        self, 
        code: str,
        target_date: Optional[date] = None
    ) -> Optional[Dict[str, Any]]:
        """
        获取分析所需的上下文数据
        
        返回今日数据 + 昨日数据的对比信息
        
        Args:
            code: 股票代码
            target_date: 目标日期（默认今天）
            
        Returns:
            包含今日数据、昨日对比等信息的字典
        """
        if target_date is None:
            target_date = date.today()
        # 注意：尽管入参提供了 target_date，但当前实现实际使用的是“最新两天数据”（get_latest_data），
        # 并不会按 target_date 精确取当日/前一交易日的上下文。
        # 因此若未来需要支持“按历史某天复盘/重算”的可解释性，这里需要调整。
        # 该行为目前保留（按需求不改逻辑）。
        
        # 获取最近2天数据
        recent_data = self.get_latest_data(code, days=5)
        recent_data = self._filter_future_dated_rows(code, recent_data)[:2]
        
        if not recent_data:
            logger.warning(f"未找到 {code} 的数据")
            return None
        
        today_data = recent_data[0]
        yesterday_data = recent_data[1] if len(recent_data) > 1 else None
        
        context = {
            'code': code,
            'date': today_data.date.isoformat(),
            'today': today_data.to_dict(),
        }
        
        if yesterday_data:
            context['yesterday'] = yesterday_data.to_dict()
            
            # 计算相比昨日的变化
            if yesterday_data.volume and yesterday_data.volume > 0:
                context['volume_change_ratio'] = round(
                    today_data.volume / yesterday_data.volume, 2
                )
            
            if yesterday_data.close and yesterday_data.close > 0:
                context['price_change_ratio'] = round(
                    (today_data.close - yesterday_data.close) / yesterday_data.close * 100, 2
                )
            
            # 均线形态判断
            context['ma_status'] = self._analyze_ma_status(today_data)
        
        return context

    @staticmethod
    def _filter_future_dated_rows(code: str, rows: List[StockDaily]) -> List[StockDaily]:
        market = get_market_for_stock(code)
        tz_name = MARKET_TIMEZONE.get(market or "")
        if not tz_name or not rows:
            return rows
        market_today = datetime.now(ZoneInfo(tz_name)).date()
        filtered = [
            row for row in rows
            if getattr(row, "date", None) is not None and row.date <= market_today
        ]
        return filtered or rows
    
    def _analyze_ma_status(self, data: StockDaily) -> str:
        """
        分析均线形态
        
        判断条件：
        - 多头排列：close > ma5 > ma10 > ma20
        - 空头排列：close < ma5 < ma10 < ma20
        - 震荡整理：其他情况
        """
        # 注意：这里的均线形态判断基于“close/ma5/ma10/ma20”静态比较，
        # 未考虑均线拐点、斜率、或不同数据源复权口径差异。
        # 该行为目前保留（按需求不改逻辑）。
        close = data.close or 0
        ma5 = data.ma5 or 0
        ma10 = data.ma10 or 0
        ma20 = data.ma20 or 0
        
        if close > ma5 > ma10 > ma20 > 0:
            return "多头排列 📈"
        elif close < ma5 < ma10 < ma20 and ma20 > 0:
            return "空头排列 📉"
        elif close > ma5 and ma5 > ma10:
            return "短期向好 🔼"
        elif close < ma5 and ma5 < ma10:
            return "短期走弱 🔽"
        else:
            return "震荡整理 ↔️"

    @staticmethod
    def _parse_published_date(value: Optional[str]) -> Optional[datetime]:
        """
        解析发布时间字符串（失败返回 None）
        """
        if not value:
            return None

        if isinstance(value, datetime):
            return value

        text = str(value).strip()
        if not text:
            return None

        # 优先尝试 ISO 格式
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            pass

        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d %H:%M",
            "%Y/%m/%d",
        ):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue

        return None

    @staticmethod
    def _safe_json_dumps(data: Any) -> str:
        """
        安全序列化为 JSON 字符串
        """
        try:
            return json.dumps(data, ensure_ascii=False, default=str)
        except Exception:
            return json.dumps(str(data), ensure_ascii=False)

    @staticmethod
    def _build_raw_result(result: Any) -> Dict[str, Any]:
        """
        生成完整分析结果字典
        """
        data = result.to_dict() if hasattr(result, "to_dict") else {}
        data.update({
            'data_sources': getattr(result, 'data_sources', ''),
            'raw_response': getattr(result, 'raw_response', None),
        })
        return data

    @staticmethod
    def _parse_sniper_value(value: Any) -> Optional[float]:
        """
        Parse a sniper point value from various formats to float.

        Handles: numeric types, plain number strings, Chinese price formats
        like "18.50元", range formats like "18.50-19.00", and text with
        embedded numbers while filtering out MA indicators.
        """
        if value is None:
            return None
        if isinstance(value, (int, float)):
            v = float(value)
            return v if v > 0 else None

        text = str(value).replace(',', '').replace('，', '').strip()
        if not text or text == '-' or text == '—' or text == 'N/A':
            return None

        # 尝试直接解析纯数字字符串
        try:
            return float(text)
        except ValueError:
            pass

        # 优先截取 "：" 到 "元" 之间的价格，避免误提取 MA5/MA10 等技术指标数字
        colon_pos = max(text.rfind("："), text.rfind(":"))
        yuan_pos = text.find("元", colon_pos + 1 if colon_pos != -1 else 0)
        if yuan_pos != -1:
            segment_start = colon_pos + 1 if colon_pos != -1 else 0
            segment = text[segment_start:yuan_pos]
            
            # 使用 finditer 并过滤掉 MA 开头的数字
            matches = list(re.finditer(r"-?\d+(?:\.\d+)?", segment))
            valid_numbers = []
            for m in matches:
                # 检查前面是否是 "MA" (忽略大小写)
                start_idx = m.start()
                if start_idx >= 2:
                    prefix = segment[start_idx-2:start_idx].upper()
                    if prefix == "MA":
                        continue
                valid_numbers.append(m.group())
            
            if valid_numbers:
                try:
                    return abs(float(valid_numbers[-1]))
                except ValueError:
                    pass

        # 兜底：无"元"字时，先截去第一个括号后的内容，避免误提取括号内技术指标数字
        # 例如 "1.52-1.53 (回踩MA5/10附近)" → 仅在 "1.52-1.53 " 中搜索
        paren_pos = len(text)
        for paren_char in ('(', '（'):
            pos = text.find(paren_char)
            if pos != -1:
                paren_pos = min(paren_pos, pos)
        search_text = text[:paren_pos].strip() or text  # 括号前为空时降级用全文

        valid_numbers = []
        for m in re.finditer(r"\d+(?:\.\d+)?", search_text):
            start_idx = m.start()
            if start_idx >= 2 and search_text[start_idx-2:start_idx].upper() == "MA":
                continue
            valid_numbers.append(m.group())
        if valid_numbers:
            try:
                return float(valid_numbers[-1])
            except ValueError:
                pass
        return None

    def _extract_sniper_points(self, result: Any) -> Dict[str, Optional[float]]:
        """
        Extract sniper point values from an AnalysisResult.

        Tries multiple extraction paths to handle different dashboard structures:
        1. result.get_sniper_points() (standard path)
        2. Direct dashboard dict traversal with various nesting levels
        3. Fallback from raw_result dict if available
        """
        raw_points = {}

        # Path 1: standard method
        if hasattr(result, "get_sniper_points"):
            raw_points = result.get_sniper_points() or {}

        # Path 2: direct dashboard traversal when standard path yields empty values
        if not any(raw_points.get(k) for k in ("ideal_buy", "secondary_buy", "stop_loss", "take_profit")):
            dashboard = getattr(result, "dashboard", None)
            if isinstance(dashboard, dict):
                raw_points = self._find_sniper_in_dashboard(dashboard) or raw_points

        # Path 3: try raw_result for agent mode results
        if not any(raw_points.get(k) for k in ("ideal_buy", "secondary_buy", "stop_loss", "take_profit")):
            raw_response = getattr(result, "raw_response", None)
            if isinstance(raw_response, dict):
                raw_points = self._find_sniper_in_dashboard(raw_response) or raw_points

        return {
            "ideal_buy": self._parse_sniper_value(raw_points.get("ideal_buy")),
            "secondary_buy": self._parse_sniper_value(raw_points.get("secondary_buy")),
            "stop_loss": self._parse_sniper_value(raw_points.get("stop_loss")),
            "take_profit": self._parse_sniper_value(raw_points.get("take_profit")),
        }

    @staticmethod
    def _find_sniper_in_dashboard(d: dict) -> Optional[Dict[str, Any]]:
        """
        Recursively search for sniper_points in a dashboard dict.
        Handles various nesting: dashboard.battle_plan.sniper_points,
        dashboard.dashboard.battle_plan.sniper_points, etc.
        """
        if not isinstance(d, dict):
            return None

        # Direct: d has sniper_points keys at top level
        if "ideal_buy" in d:
            return d

        # d.sniper_points
        sp = d.get("sniper_points")
        if isinstance(sp, dict) and sp:
            return sp

        # d.battle_plan.sniper_points
        bp = d.get("battle_plan")
        if isinstance(bp, dict):
            sp = bp.get("sniper_points")
            if isinstance(sp, dict) and sp:
                return sp

        # d.dashboard.battle_plan.sniper_points (double-nested)
        inner = d.get("dashboard")
        if isinstance(inner, dict):
            bp = inner.get("battle_plan")
            if isinstance(bp, dict):
                sp = bp.get("sniper_points")
                if isinstance(sp, dict) and sp:
                    return sp

        return None

    @staticmethod
    def _build_fallback_url_key(
        code: str,
        title: str,
        source: str,
        published_date: Optional[datetime]
    ) -> str:
        """
        生成无 URL 时的去重键（确保稳定且较短）
        """
        date_str = published_date.isoformat() if published_date else ""
        raw_key = f"{code}|{title}|{source}|{date_str}"
        digest = hashlib.md5(raw_key.encode("utf-8")).hexdigest()
        return f"no-url:{code}:{digest}"

    def ensure_conversation_session(
        self,
        session_id: str,
        *,
        owner_id: Optional[str] = None,
        title: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> ConversationSessionRecord:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            raise ValueError("session_id is required")
        resolved_owner_id = self.require_user_id(owner_id)

        def _upsert(active_session: Session) -> ConversationSessionRecord:
            row = active_session.execute(
                select(ConversationSessionRecord)
                .where(ConversationSessionRecord.session_id == normalized_session_id)
                .limit(1)
            ).scalar_one_or_none()
            if row is None:
                row = ConversationSessionRecord(
                    session_id=normalized_session_id,
                    owner_id=resolved_owner_id,
                    title=(title or "").strip()[:255] or None,
                )
                active_session.add(row)
                active_session.flush()
            else:
                if resolved_owner_id and row.owner_id and resolved_owner_id != row.owner_id:
                    raise ValueError(
                        f"Conversation session {normalized_session_id} belongs to another owner"
                    )
                if row.owner_id is None:
                    row.owner_id = resolved_owner_id
                if title and not row.title:
                    row.title = title.strip()[:255] or row.title
                row.updated_at = datetime.now()
                active_session.flush()
            return row

        if session is not None:
            return _upsert(session)
        with self.session_scope() as active_session:
            return _upsert(active_session)

    def save_conversation_message(
        self,
        session_id: str,
        role: str,
        content: str,
        owner_id: Optional[str] = None,
    ) -> None:
        """
        保存 Agent 对话消息
        """
        resolved_owner_id = self.require_user_id(owner_id)
        with self.session_scope() as session:
            session_row = self.ensure_conversation_session(
                session_id,
                owner_id=resolved_owner_id,
                title=content if role == "user" else None,
                session=session,
            )
            msg = ConversationMessage(
                session_id=session_id,
                role=role,
                content=content
            )
            session.add(msg)
            session_row.updated_at = datetime.now()
            if role == "user" and not session_row.title:
                session_row.title = str(content or "").strip()[:255] or None
            session.flush()
            if self._phase_b_enabled and self._phase_b_store is not None:
                self._phase_b_store.append_chat_message_shadow(
                    session_key=session_id,
                    owner_user_id=resolved_owner_id,
                    role=role,
                    content=content,
                    title_hint=content if role == "user" else None,
                    created_at=msg.created_at,
                )

    def get_conversation_history(
        self,
        session_id: str,
        limit: int = 20,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        获取 Agent 对话历史
        """
        with self.session_scope() as session:
            if not include_all_owners:
                self._require_conversation_session_access(
                    session=session,
                    session_id=session_id,
                    owner_id=owner_id,
                )
            stmt = select(ConversationMessage).filter(
                ConversationMessage.session_id == session_id
            ).order_by(ConversationMessage.created_at.desc()).limit(limit)
            messages = session.execute(stmt).scalars().all()

            # 倒序返回，保证时间顺序
            return [{"role": msg.role, "content": msg.content} for msg in reversed(messages)]

    def conversation_session_exists(self, session_id: str) -> bool:
        """Return True when at least one message exists for the given session."""
        with self.session_scope() as session:
            stmt = (
                select(ConversationSessionRecord.id)
                .where(ConversationSessionRecord.session_id == session_id)
                .limit(1)
            )
            return session.execute(stmt).scalar() is not None

    def get_chat_sessions(
        self,
        limit: int = 50,
        session_prefix: Optional[str] = None,
        extra_session_ids: Optional[List[str]] = None,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        获取聊天会话列表（从 conversation_messages 聚合）

        Args:
            limit: Maximum number of sessions to return.
            session_prefix: If provided, only return sessions whose session_id
                starts with this prefix.  Used for per-user isolation (e.g.
                ``"telegram_12345"``).
            extra_session_ids: Optional exact session ids to include in
                addition to the scoped prefix.

        Returns:
            按最近活跃时间倒序的会话列表，每条包含 session_id, title, message_count, last_active
        """
        with self.session_scope() as session:
            normalized_prefix = None
            if session_prefix:
                normalized_prefix = session_prefix if session_prefix.endswith(":") else f"{session_prefix}:"
            exact_ids = [sid for sid in (extra_session_ids or []) if sid]

            ownership_conditions = []
            if not include_all_owners:
                ownership_conditions.append(
                    ConversationSessionRecord.owner_id == self.require_user_id(owner_id)
                )
            session_id_filters = []
            if normalized_prefix:
                session_id_filters.append(
                    ConversationSessionRecord.session_id.startswith(normalized_prefix)
                )
            if exact_ids:
                session_id_filters.append(ConversationSessionRecord.session_id.in_(exact_ids))
            query = select(ConversationSessionRecord)
            if ownership_conditions:
                query = query.where(and_(*ownership_conditions))
            if session_id_filters:
                query = query.where(or_(*session_id_filters))
            stmt = (
                query
                .order_by(desc(ConversationSessionRecord.updated_at), desc(ConversationSessionRecord.id))
                .limit(limit)
            )
            rows = session.execute(stmt).scalars().all()

            results = []
            for row in rows:
                sid = row.session_id
                message_count = int(
                    session.execute(
                        select(func.count(ConversationMessage.id))
                        .where(ConversationMessage.session_id == sid)
                    ).scalar() or 0
                )
                title = ((row.title or "新对话")[:60]) if row.title else "新对话"

                results.append({
                    "session_id": sid,
                    "title": title,
                    "message_count": message_count,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "last_active": row.updated_at.isoformat() if row.updated_at else None,
                })
            return results

    def get_conversation_messages(
        self,
        session_id: str,
        limit: int = 100,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        获取单个会话的完整消息列表（用于前端恢复历史）
        """
        with self.session_scope() as session:
            if not include_all_owners:
                self._require_conversation_session_access(
                    session=session,
                    session_id=session_id,
                    owner_id=owner_id,
                )
            stmt = (
                select(ConversationMessage)
                .where(ConversationMessage.session_id == session_id)
                .order_by(ConversationMessage.created_at)
                .limit(limit)
            )
            messages = session.execute(stmt).scalars().all()
            return [
                {
                    "id": str(msg.id),
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat() if msg.created_at else None,
                }
                for msg in messages
            ]

    def delete_conversation_session(
        self,
        session_id: str,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> int:
        """
        删除指定会话的所有消息

        Returns:
            删除的消息数
        """
        with self.session_scope() as session:
            if not include_all_owners:
                self._require_conversation_session_access(
                    session=session,
                    session_id=session_id,
                    owner_id=owner_id,
                )
            if self._phase_b_enabled and self._phase_b_store is not None:
                self._phase_b_store.delete_chat_session_shadow(
                    session_id,
                    owner_user_id=None if include_all_owners else self.require_user_id(owner_id),
                )
            result = session.execute(
                delete(ConversationMessage).where(
                    ConversationMessage.session_id == session_id
                )
            )
            session.execute(
                delete(ConversationSessionRecord).where(
                    ConversationSessionRecord.session_id == session_id
                )
            )
            return result.rowcount

    def _require_conversation_session_access(
        self,
        *,
        session: Session,
        session_id: str,
        owner_id: Optional[str] = None,
    ) -> ConversationSessionRecord:
        resolved_owner_id = self.require_user_id(owner_id)
        row = session.execute(
            select(ConversationSessionRecord)
            .where(
                and_(
                    ConversationSessionRecord.session_id == session_id,
                    ConversationSessionRecord.owner_id == resolved_owner_id,
                )
            )
            .limit(1)
        ).scalar_one_or_none()
        if row is None:
            raise ValueError(f"Conversation session not found for owner: {session_id}")
        return row

    # ------------------------------------------------------------------
    # LLM usage tracking
    # ------------------------------------------------------------------

    def record_llm_usage(
        self,
        call_type: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        stock_code: Optional[str] = None,
    ) -> None:
        """Append one LLM call record to llm_usage."""
        row = LLMUsage(
            call_type=call_type,
            model=model or "unknown",
            stock_code=stock_code,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )
        with self.session_scope() as session:
            session.add(row)

    def get_llm_usage_summary(
        self,
        from_dt: datetime,
        to_dt: datetime,
    ) -> Dict[str, Any]:
        """Return aggregated token usage between from_dt and to_dt.

        Returns a dict with keys:
          total_calls, total_tokens,
          by_call_type: list of {call_type, calls, total_tokens},
          by_model:     list of {model, calls, total_tokens}
        """
        with self.session_scope() as session:
            base_filter = and_(
                LLMUsage.called_at >= from_dt,
                LLMUsage.called_at <= to_dt,
            )

            # Overall totals
            totals = session.execute(
                select(
                    func.count(LLMUsage.id).label("calls"),
                    func.coalesce(func.sum(LLMUsage.total_tokens), 0).label("tokens"),
                ).where(base_filter)
            ).one()

            # Breakdown by call_type
            by_type_rows = session.execute(
                select(
                    LLMUsage.call_type,
                    func.count(LLMUsage.id).label("calls"),
                    func.coalesce(func.sum(LLMUsage.total_tokens), 0).label("tokens"),
                )
                .where(base_filter)
                .group_by(LLMUsage.call_type)
                .order_by(desc(func.sum(LLMUsage.total_tokens)))
            ).all()

            # Breakdown by model
            by_model_rows = session.execute(
                select(
                    LLMUsage.model,
                    func.count(LLMUsage.id).label("calls"),
                    func.coalesce(func.sum(LLMUsage.total_tokens), 0).label("tokens"),
                )
                .where(base_filter)
                .group_by(LLMUsage.model)
                .order_by(desc(func.sum(LLMUsage.total_tokens)))
            ).all()

        return {
            "total_calls": totals.calls,
            "total_tokens": totals.tokens,
            "by_call_type": [
                {"call_type": r.call_type, "calls": r.calls, "total_tokens": r.tokens}
                for r in by_type_rows
            ],
            "by_model": [
                {"model": r.model, "calls": r.calls, "total_tokens": r.tokens}
                for r in by_model_rows
            ],
        }


# 便捷函数
def get_db() -> DatabaseManager:
    """获取数据库管理器实例的快捷方式"""
    return DatabaseManager.get_instance()


def persist_llm_usage(
    usage: Dict[str, Any],
    model: str,
    call_type: str,
    stock_code: Optional[str] = None,
    *,
    owner_user_id: Optional[str] = None,
    guest_bucket_hash: Optional[str] = None,
    route_family: Optional[str] = None,
    provider: Optional[str] = None,
    cached_input_tokens: Optional[int] = None,
    quota_reservation_id: Optional[str] = None,
    request_hash: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Fire-and-forget: write one LLM call record to llm_usage. Never raises."""
    prompt_tokens = usage.get("prompt_tokens", 0) or 0
    completion_tokens = usage.get("completion_tokens", 0) or 0
    total_tokens = usage.get("total_tokens", 0) or 0
    try:
        db = DatabaseManager.get_instance()
        db.record_llm_usage(
            call_type=call_type,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            stock_code=stock_code,
        )
    except Exception as exc:
        logging.getLogger(__name__).warning("[LLM usage] failed to persist usage record: %s", exc)
        return
    _reconcile_llm_usage_cost_ledger(
        owner_user_id=owner_user_id,
        guest_bucket_hash=guest_bucket_hash,
        route_family=route_family or call_type,
        call_type=call_type,
        provider=provider or _provider_from_llm_model(model),
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cached_input_tokens=cached_input_tokens,
        quota_reservation_id=quota_reservation_id,
        request_hash=request_hash,
        metadata=metadata,
    )


def _reconcile_llm_usage_cost_ledger(
    *,
    owner_user_id: Optional[str],
    guest_bucket_hash: Optional[str],
    route_family: str,
    call_type: str,
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    cached_input_tokens: Optional[int],
    quota_reservation_id: Optional[str],
    request_hash: Optional[str],
    metadata: Optional[Dict[str, Any]],
) -> None:
    """Best-effort observer that mirrors normalized usage into the cost ledger."""
    try:
        from src.services.llm_cost_ledger_service import LlmCostLedgerService

        LlmCostLedgerService().reconcile_usage(
            owner_user_id=owner_user_id,
            guest_bucket_hash=guest_bucket_hash,
            route_family=route_family,
            call_type=call_type,
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cached_input_tokens=cached_input_tokens,
            quota_reservation_id=quota_reservation_id,
            request_hash=request_hash,
            metadata=metadata,
        )
    except Exception as exc:
        logging.getLogger(__name__).debug(
            "[LLM cost ledger] usage reconciliation skipped: %s",
            type(exc).__name__,
        )


def _provider_from_llm_model(model: Any) -> str:
    raw = str(model or "").strip().lower()
    if "/" in raw:
        return raw.split("/", 1)[0] or "unknown"
    if raw:
        return raw.split("-", 1)[0] or "unknown"
    return "unknown"


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.DEBUG)
    
    db = get_db()
    
    print("=== 数据库测试 ===")
    print(f"数据库初始化成功")
    
    # 测试检查今日数据
    has_data = db.has_today_data('600519')
    print(f"茅台今日是否有数据: {has_data}")
    
    # 测试保存数据
    test_df = pd.DataFrame({
        'date': [date.today()],
        'open': [1800.0],
        'high': [1850.0],
        'low': [1780.0],
        'close': [1820.0],
        'volume': [10000000],
        'amount': [18200000000],
        'pct_chg': [1.5],
        'ma5': [1810.0],
        'ma10': [1800.0],
        'ma20': [1790.0],
        'volume_ratio': [1.2],
    })
    
    saved = db.save_daily_data(test_df, '600519', 'TestSource')
    print(f"保存测试数据: {saved} 条")
    
    # 测试获取上下文
    context = db.get_analysis_context('600519')
    print(f"分析上下文: {context}")
