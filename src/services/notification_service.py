# -*- coding: utf-8 -*-
"""Admin operational notification channels and in-app notification events."""

from __future__ import annotations

import json
import logging
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import desc, select

from src.config import get_config
from src.notification import NotificationChannel as SystemNotificationChannel
from src.notification import NotificationService as SystemNotificationService
from src.storage import NotificationChannel, NotificationEvent, get_db

logger = logging.getLogger(__name__)

SEVERITY_ORDER = {"info": 10, "warning": 20, "critical": 30}
LOG_LEVEL_TO_SEVERITY = {
    "NOTICE": "info",
    "WARNING": "warning",
    "ERROR": "critical",
    "CRITICAL": "critical",
}
CHANNEL_TYPES = {"in_app", "webhook", "system_channel"}
MASKED_VALUE = "********"
SENSITIVE_KEYS = ("secret", "token", "password", "authorization", "bearer")
SSL_CERTIFICATE_ERROR_RE = re.compile(
    r"certificate verify failed|CERTIFICATE_VERIFY_FAILED|ssl certificate verification failed|"
    r"ssl 证书.*失败|证书.*验证失败|证书校验失败",
    re.IGNORECASE,
)
SSL_TIMEOUT_ERROR_RE = re.compile(r"timed out|timeout|超时", re.IGNORECASE)


class NotificationDeliveryClient:
    """Outbound delivery adapter; tests replace this with a fake client."""

    @staticmethod
    def _ssl_context(url: str) -> Optional[ssl.SSLContext]:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https":
            return None
        verify_ssl = bool(getattr(get_config(), "webhook_verify_ssl", True))
        if not verify_ssl:
            logger.warning("webhook SSL certificate verification is disabled by WEBHOOK_VERIFY_SSL=false")
            return ssl._create_unverified_context()
        try:
            import certifi

            return ssl.create_default_context(cafile=certifi.where())
        except Exception:
            return ssl.create_default_context()

    def send_webhook(
        self,
        *,
        url: str,
        payload: dict,
        headers: Optional[dict] = None,
        timeout: float = 5.0,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                **(headers or {}),
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout, context=self._ssl_context(url)) as response:
                status = int(getattr(response, "status", 200) or 200)
                if status >= 400:
                    raise RuntimeError(f"webhook returned HTTP {status}")
        except ssl.SSLCertVerificationError as exc:
            raise RuntimeError(f"SSL certificate verification failed: {exc}") from exc
        except ssl.SSLError as exc:
            if SSL_CERTIFICATE_ERROR_RE.search(str(exc)):
                raise RuntimeError(f"SSL certificate verification failed: {exc}") from exc
            raise RuntimeError(f"SSL error while delivering webhook: {exc}") from exc
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", None)
            if isinstance(reason, ssl.SSLCertVerificationError) or SSL_CERTIFICATE_ERROR_RE.search(str(reason or exc)):
                raise RuntimeError(f"SSL certificate verification failed: {reason or exc}") from exc
            raise RuntimeError(str(exc)) from exc


def _safe_json_loads(value: Any, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except Exception:
        return fallback


def _safe_json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _utcnow() -> datetime:
    return datetime.utcnow()


def _normalize_severity(value: str) -> str:
    severity = str(value or "").strip().lower()
    if severity not in SEVERITY_ORDER:
        raise ValueError("severity must be info, warning, or critical")
    return severity


def _normalize_channel_type(value: str) -> str:
    channel_type = str(value or "").strip().lower()
    if channel_type not in CHANNEL_TYPES:
        raise ValueError("channel type must be in_app, webhook, or system_channel")
    return channel_type


def _normalize_system_channel(value: Any) -> str:
    channel = str(value or "").strip().lower()
    if not channel:
        raise ValueError("config.channel is required for system_channel")
    try:
        SystemNotificationChannel(channel)
    except ValueError as exc:
        raise ValueError(f"unsupported system notification channel: {channel}") from exc
    return channel


def _severity_from_log_level(value: Any) -> Optional[str]:
    level = str(value or "").strip().upper()
    return LOG_LEVEL_TO_SEVERITY.get(level)


def _validate_webhook_url(value: Any) -> str:
    url = str(value or "").strip()
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("webhook_url must be a valid http or https URL")
    return url


def _mask_webhook_url(value: Any) -> str:
    url = str(value or "").strip()
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}/***"
    return MASKED_VALUE if url else ""


def _mask_config(config: Dict[str, Any]) -> Dict[str, Any]:
    masked: Dict[str, Any] = {}
    for key, value in (config or {}).items():
        key_text = str(key)
        lower_key = key_text.lower()
        if key_text == "webhook_url":
            masked[key_text] = _mask_webhook_url(value)
        elif any(token in lower_key for token in SENSITIVE_KEYS):
            masked[key_text] = MASKED_VALUE if value else ""
        else:
            masked[key_text] = value
    return masked


def _classify_delivery_error(message: Any) -> Dict[str, Any]:
    error_text = str(message or "").strip()
    if not error_text:
        return {"code": None, "diagnostics": {}}

    if SSL_CERTIFICATE_ERROR_RE.search(error_text):
        return {
            "code": "ssl_certificate_verify_failed",
            "diagnostics": {
                "summary_en": "SSL certificate verification failed.",
                "summary_zh": "SSL 证书校验失败。",
                "action_en": "Check the webhook certificate chain, trusted CA, and hostname.",
                "action_zh": "请检查 webhook 证书链、受信任 CA 和主机名是否匹配。",
                "raw_message": error_text,
            },
        }

    if SSL_TIMEOUT_ERROR_RE.search(error_text):
        return {
            "code": "webhook_timeout",
            "diagnostics": {
                "summary_en": "Webhook delivery timed out.",
                "summary_zh": "Webhook 投递超时。",
                "action_en": "Check webhook availability, DNS, proxy, and upstream latency.",
                "action_zh": "请检查 webhook 可用性、DNS、代理和上游延迟。",
                "raw_message": error_text,
            },
        }

    return {
        "code": "webhook_delivery_failed",
        "diagnostics": {
            "raw_message": error_text,
        },
    }


class NotificationService:
    """CRUD, test delivery, event emission, and acknowledgement."""

    def __init__(
        self,
        *,
        db: Any = None,
        delivery_client: Optional[NotificationDeliveryClient] = None,
    ) -> None:
        self.db = db or get_db()
        self.delivery_client = delivery_client or NotificationDeliveryClient()

    def list_channels(self) -> List[Dict[str, Any]]:
        with self.db.get_session() as session:
            rows = session.execute(select(NotificationChannel).order_by(NotificationChannel.created_at.desc())).scalars().all()
            return [self._channel_payload(row) for row in rows]

    def list_system_channels(self) -> List[str]:
        return [channel.value for channel in SystemNotificationService().get_available_channels()]

    def create_channel(
        self,
        *,
        name: str,
        type: str,
        enabled: bool = True,
        severity_min: str = "warning",
        event_types: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        clean = self._validate_channel_input(
            name=name,
            type=type,
            severity_min=severity_min,
            event_types=event_types,
            config=config,
        )
        now = _utcnow()
        with self.db.session_scope() as session:
            row = NotificationChannel(
                name=clean["name"],
                type=clean["type"],
                enabled=bool(enabled),
                severity_min=clean["severity_min"],
                event_types_json=_safe_json_dumps(clean["event_types"]),
                config_json=_safe_json_dumps(clean["config"]),
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            session.flush()
            return self._channel_payload(row)

    def update_channel(
        self,
        channel_id: int,
        *,
        name: Optional[str] = None,
        type: Optional[str] = None,
        enabled: Optional[bool] = None,
        severity_min: Optional[str] = None,
        event_types: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        with self.db.session_scope() as session:
            row = self._get_channel_row(session, channel_id)
            current_config = _safe_json_loads(row.config_json, {})
            merged_config = dict(current_config)
            for key, value in (config or {}).items():
                if value == MASKED_VALUE:
                    continue
                merged_config[key] = value
            clean = self._validate_channel_input(
                name=name if name is not None else row.name,
                type=type if type is not None else row.type,
                severity_min=severity_min if severity_min is not None else row.severity_min,
                event_types=event_types if event_types is not None else _safe_json_loads(row.event_types_json, []),
                config=merged_config,
            )
            row.name = clean["name"]
            row.type = clean["type"]
            if enabled is not None:
                row.enabled = bool(enabled)
            row.severity_min = clean["severity_min"]
            row.event_types_json = _safe_json_dumps(clean["event_types"])
            row.config_json = _safe_json_dumps(clean["config"])
            row.updated_at = _utcnow()
            row.last_error = None
            session.flush()
            return self._channel_payload(row)

    def delete_channel(self, channel_id: int) -> None:
        with self.db.session_scope() as session:
            row = self._get_channel_row(session, channel_id)
            session.delete(row)

    def test_channel(self, channel_id: int) -> Dict[str, Any]:
        with self.db.session_scope() as session:
            row = self._get_channel_row(session, channel_id)
            now = _utcnow()
            try:
                self._deliver_to_channel(
                    row,
                    {
                        "event_type": "notification.test",
                        "severity": "info",
                        "title": "Test notification",
                        "message": "Admin notification channel test",
                        "payload": {},
                    },
                )
                row.last_tested_at = now
                row.last_sent_at = now
                row.last_error = None
                return {"success": True, "channel": self._channel_payload(row)}
            except Exception as exc:
                classification = _classify_delivery_error(exc)
                row.last_tested_at = now
                row.last_error = str(exc)
                logger.warning("notification channel test failed: %s", exc)
                return {
                    "success": False,
                    "error": str(exc),
                    "error_code": classification["code"],
                    "diagnostics": classification["diagnostics"],
                    "channel": self._channel_payload(row),
                }

    def emit_event(
        self,
        *,
        event_type: str,
        severity: str,
        title: str,
        message: str,
        payload: Optional[Dict[str, Any]] = None,
        fingerprint: Optional[str] = None,
        dedupe_window: timedelta = timedelta(minutes=30),
    ) -> Dict[str, Any]:
        severity_value = _normalize_severity(severity)
        event_type_value = str(event_type or "").strip()
        title_value = str(title or "").strip()
        message_value = str(message or "").strip()
        if not event_type_value:
            raise ValueError("event_type is required")
        if not title_value:
            raise ValueError("title is required")
        fingerprint_value = str(fingerprint or title_value).strip()
        dedupe_key = f"{event_type_value}:{severity_value}:{fingerprint_value}"
        now = _utcnow()
        cutoff = now - dedupe_window
        with self.db.session_scope() as session:
            existing = session.execute(
                select(NotificationEvent)
                .where(NotificationEvent.dedupe_key == dedupe_key, NotificationEvent.created_at >= cutoff)
                .order_by(desc(NotificationEvent.created_at))
                .limit(1)
            ).scalar_one_or_none()
            if existing is not None:
                data = self._event_payload(existing)
                data["deduped"] = True
                return data

            row = NotificationEvent(
                event_type=event_type_value,
                severity=severity_value,
                title=title_value[:160],
                message=message_value,
                payload_json=_safe_json_dumps(payload or {}),
                fingerprint=fingerprint_value[:160],
                dedupe_key=dedupe_key[:255],
                delivery_status="pending",
                created_at=now,
            )
            session.add(row)
            session.flush()
            delivery_status = self._deliver_event(session, row)
            row.delivery_status = delivery_status
            session.flush()
            data = self._event_payload(row)
            data["deduped"] = False
            return data

    def emit_log_event(
        self,
        *,
        log_level: str,
        category: str,
        event_name: str,
        message: Optional[str] = None,
        session_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        dedupe_window: timedelta = timedelta(minutes=30),
    ) -> Optional[Dict[str, Any]]:
        severity = _severity_from_log_level(log_level)
        if severity is None:
            return None
        event_type = "admin_logs.event"
        fingerprint = f"{session_id or 'unknown'}:{category or 'system'}:{event_name or log_level}:{message or ''}"[:160]
        if not self._has_matching_channel(event_type=event_type, severity=severity):
            return None
        return self.emit_event(
            event_type=event_type,
            severity=severity,
            title=f"Admin Log {str(log_level or '').strip().upper()}: {event_name or category or 'event'}",
            message=str(message or "").strip(),
            payload={
                "log_level": str(log_level or "").strip().upper(),
                "category": str(category or "system").strip() or "system",
                "event_name": str(event_name or "").strip(),
                "session_id": str(session_id or "").strip() or None,
                **(payload or {}),
            },
            fingerprint=fingerprint,
            dedupe_window=dedupe_window,
        )

    def list_events(
        self,
        *,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
        include_acknowledged: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        with self.db.get_session() as session:
            stmt = select(NotificationEvent)
            if event_type:
                stmt = stmt.where(NotificationEvent.event_type == event_type)
            if severity:
                stmt = stmt.where(NotificationEvent.severity == _normalize_severity(severity))
            if not include_acknowledged:
                stmt = stmt.where(NotificationEvent.acknowledged_at.is_(None))
            rows = session.execute(
                stmt.order_by(desc(NotificationEvent.created_at)).offset(max(0, int(offset))).limit(max(1, min(int(limit), 200)))
            ).scalars().all()
            total = len(session.execute(stmt).scalars().all())
            return {
                "total": total,
                "items": [self._event_payload(row) for row in rows],
                "limit": max(1, min(int(limit), 200)),
                "offset": max(0, int(offset)),
            }

    def acknowledge_event(self, event_id: int, *, acknowledged_by: str) -> Dict[str, Any]:
        with self.db.session_scope() as session:
            row = session.get(NotificationEvent, int(event_id))
            if row is None:
                raise KeyError(f"notification event not found: {event_id}")
            row.acknowledged_at = _utcnow()
            row.acknowledged_by = str(acknowledged_by or "").strip() or None
            session.flush()
            return self._event_payload(row)

    def _deliver_event(self, session: Any, event: NotificationEvent) -> str:
        rows = session.execute(select(NotificationChannel).where(NotificationChannel.enabled.is_(True))).scalars().all()
        matching = [row for row in rows if self._channel_matches(row, event)]
        if not matching:
            return "no_channels"
        successes = 0
        failures = 0
        payload = self._event_payload(event)
        for channel in matching:
            try:
                self._deliver_to_channel(channel, payload)
                channel.last_sent_at = _utcnow()
                channel.last_error = None
                successes += 1
            except Exception as exc:
                channel.last_error = str(exc)
                failures += 1
                logger.warning("notification delivery failed for channel %s: %s", channel.id, exc)
        if successes and failures:
            return "partial"
        if failures:
            return "failed"
        return "delivered"

    def _has_matching_channel(self, *, event_type: str, severity: str) -> bool:
        with self.db.get_session() as session:
            rows = session.execute(select(NotificationChannel).where(NotificationChannel.enabled.is_(True))).scalars().all()
            probe = NotificationEvent(
                event_type=event_type,
                severity=_normalize_severity(severity),
                title="probe",
                delivery_status="pending",
                created_at=_utcnow(),
            )
            return any(self._channel_matches(row, probe) for row in rows)

    def _deliver_to_channel(self, channel: NotificationChannel, payload: Dict[str, Any]) -> None:
        config = _safe_json_loads(channel.config_json, {})
        if channel.type == "in_app":
            return
        if channel.type == "webhook":
            url = _validate_webhook_url(config.get("webhook_url"))
            headers: Dict[str, str] = {}
            token = str(config.get("token") or "").strip()
            if token:
                headers["Authorization"] = f"Bearer {token}"
            self.delivery_client.send_webhook(url=url, payload=payload, headers=headers, timeout=5.0)
            return
        if channel.type == "system_channel":
            system_channel = _normalize_system_channel(config.get("channel"))
            content = self._format_system_channel_message(payload)
            sent = SystemNotificationService(channel_allowlist=[system_channel]).send(
                content,
                email_send_to_all=True,
            )
            if not sent:
                raise RuntimeError(f"system notification channel did not accept message: {system_channel}")
            return
        raise ValueError(f"unsupported channel type: {channel.type}")

    def _format_system_channel_message(self, payload: Dict[str, Any]) -> str:
        severity = str(payload.get("severity") or "info").upper()
        event_type = str(payload.get("event_type") or "")
        title = str(payload.get("title") or "Admin notification")
        message = str(payload.get("message") or "")
        event_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
        lines = [
            f"**[{severity}] {title}**",
            "",
            f"- Event: `{event_type}`",
        ]
        log_level = event_payload.get("log_level")
        category = event_payload.get("category")
        event_name = event_payload.get("event_name")
        session_id = event_payload.get("session_id")
        if log_level:
            lines.append(f"- Log level: `{log_level}`")
        if category:
            lines.append(f"- Category: `{category}`")
        if event_name:
            lines.append(f"- Log event: `{event_name}`")
        if session_id:
            lines.append(f"- Session: `{session_id}`")
        if message:
            lines.extend(["", message])
        return "\n".join(lines)

    def _channel_matches(self, channel: NotificationChannel, event: NotificationEvent) -> bool:
        if SEVERITY_ORDER.get(event.severity, 0) < SEVERITY_ORDER.get(channel.severity_min, 20):
            return False
        event_types = _safe_json_loads(channel.event_types_json, [])
        if event_types and event.event_type not in event_types:
            return False
        return True

    def _validate_channel_input(
        self,
        *,
        name: str,
        type: str,
        severity_min: str,
        event_types: Optional[Iterable[str]],
        config: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        name_value = str(name or "").strip()
        if not name_value:
            raise ValueError("name is required")
        channel_type = _normalize_channel_type(type)
        severity_value = _normalize_severity(severity_min)
        event_type_values = [str(item).strip() for item in (event_types or []) if str(item).strip()]
        config_value = dict(config or {})
        if channel_type == "webhook":
            config_value["webhook_url"] = _validate_webhook_url(config_value.get("webhook_url"))
        if channel_type == "system_channel":
            config_value = {"channel": _normalize_system_channel(config_value.get("channel"))}
        return {
            "name": name_value[:80],
            "type": channel_type,
            "severity_min": severity_value,
            "event_types": event_type_values,
            "config": config_value,
        }

    def _get_channel_row(self, session: Any, channel_id: int) -> NotificationChannel:
        row = session.get(NotificationChannel, int(channel_id))
        if row is None:
            raise KeyError(f"notification channel not found: {channel_id}")
        return row

    def _channel_payload(self, row: NotificationChannel) -> Dict[str, Any]:
        config = _safe_json_loads(row.config_json, {})
        error_classification = _classify_delivery_error(row.last_error)
        return {
            "id": row.id,
            "name": row.name,
            "type": row.type,
            "enabled": bool(row.enabled),
            "severity_min": row.severity_min,
            "event_types": _safe_json_loads(row.event_types_json, []),
            "config": _mask_config(config),
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            "last_tested_at": row.last_tested_at.isoformat() if row.last_tested_at else None,
            "last_sent_at": row.last_sent_at.isoformat() if row.last_sent_at else None,
            "last_error": row.last_error,
            "last_error_code": error_classification["code"],
            "last_error_diagnostics": error_classification["diagnostics"],
        }

    def _event_payload(self, row: NotificationEvent) -> Dict[str, Any]:
        return {
            "id": row.id,
            "event_type": row.event_type,
            "severity": row.severity,
            "title": row.title,
            "message": row.message or "",
            "payload": _safe_json_loads(row.payload_json, {}),
            "fingerprint": row.fingerprint,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "acknowledged_at": row.acknowledged_at.isoformat() if row.acknowledged_at else None,
            "acknowledged_by": row.acknowledged_by,
            "delivery_status": row.delivery_status,
        }
