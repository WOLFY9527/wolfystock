# -*- coding: utf-8 -*-
"""Small admin-governance audit helper for sensitive admin views."""

from __future__ import annotations

import logging
from typing import Any

from src.auth_context import AdminActorContext
from src.services.execution_log_service import ExecutionLogService
from src.utils.security import sanitize_metadata, sanitize_message

logger = logging.getLogger(__name__)


class AdminGovernanceAuditService:
    """Record bounded, sanitized admin view events through execution logs."""

    ALLOWED_ACTIONS = {
        "admin_portfolio.summary_viewed",
        "admin_portfolio.holdings_viewed",
        "admin_portfolio.activity_viewed",
        "admin_portfolio.account_detail_viewed",
        "admin_security.account_disabled",
        "admin_security.account_enabled",
        "admin_security.sessions_revoked",
    }

    def __init__(self, execution_logs: ExecutionLogService | None = None):
        self.execution_logs = execution_logs or ExecutionLogService()

    def record_view(
        self,
        *,
        action: str,
        actor: AdminActorContext,
        target_user_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        if action not in self.ALLOWED_ACTIONS:
            raise ValueError(f"Unsupported admin audit action: {action}")
        safe_metadata = sanitize_metadata(
            {
                "target_user_id": str(target_user_id or "").strip(),
                "route_family": "admin_portfolio",
                **(metadata or {}),
            }
        )
        actor_payload = {
            "user_id": actor.user_id,
            "username": actor.username,
            "display_name": actor.display_name,
            "role": "admin" if actor.is_admin else actor.role,
            "actor_type": "admin" if actor.is_admin else "user",
        }
        try:
            return self.execution_logs.record_admin_action(
                action=action,
                message=sanitize_message(f"Admin portfolio view: {action}"),
                actor=actor_payload,
                subsystem="portfolio",
                destructive=False,
                detail=safe_metadata,
                overall_status="completed",
                result={
                    "target_user_id": str(target_user_id or "").strip(),
                    "event": action,
                    "metadata": safe_metadata,
                },
            )
        except Exception as exc:
            logger.warning("Record admin governance audit failed: %s", exc)
            return None

    def record_action(
        self,
        *,
        action: str,
        actor: AdminActorContext,
        target_user_id: str,
        reason: str,
        subsystem: str,
        destructive: bool,
        overall_status: str,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        if action not in self.ALLOWED_ACTIONS:
            raise ValueError(f"Unsupported admin audit action: {action}")
        safe_metadata = sanitize_metadata(
            {
                "target_user_id": str(target_user_id or "").strip(),
                "reason": str(reason or "").strip()[:500],
                **(metadata or {}),
            }
        )
        actor_payload = {
            "user_id": actor.user_id,
            "username": actor.username,
            "display_name": actor.display_name,
            "role": "admin" if actor.is_admin else actor.role,
            "actor_type": "admin" if actor.is_admin else "user",
        }
        try:
            return self.execution_logs.record_admin_action(
                action=action,
                message=sanitize_message(f"Admin security action: {action}"),
                actor=actor_payload,
                subsystem=subsystem,
                destructive=destructive,
                detail=safe_metadata,
                overall_status=overall_status,
                result={
                    "target_user_id": str(target_user_id or "").strip(),
                    "event": action,
                    "metadata": safe_metadata,
                },
            )
        except Exception as exc:
            logger.warning("Record admin governance audit action failed: %s", exc)
            return None
