# -*- coding: utf-8 -*-
"""Dry-run provider circuit observation helper.

This helper records synthetic provider circuit counters and events only. It does
not read circuit state for enforcement and does not change provider order,
fallback, retry, timeout, or cache behavior.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from src.storage import DatabaseManager


class ProviderCircuitObserver:
    """Record sanitized provider circuit observations through storage helpers."""

    RESULT_BUCKETS = {
        "success",
        "timeout",
        "provider_429",
        "provider_403",
        "provider_5xx",
        "network_error",
        "malformed_payload",
        "insufficient_payload",
        "auth_or_key_invalid",
        "quota_policy_block",
        "operator_disabled",
    }
    FAILURE_BUCKETS = RESULT_BUCKETS - {"success"}
    REJECTED_BUCKETS = {"quota_policy_block", "operator_disabled"}

    def __init__(self, *, db: Optional[DatabaseManager] = None) -> None:
        self.db = db or DatabaseManager.get_instance()

    def record_observation(
        self,
        *,
        provider: str,
        result_bucket: str,
        provider_category: Optional[str] = None,
        route_family: Optional[str] = None,
        policy_key: Optional[str] = "provider_circuit_dry_run_v1",
        window_type: str = "hour",
        owner_user_id: Optional[str] = None,
        guest_bucket_hash: Optional[str] = None,
        duration_ms: Optional[int] = None,
        probe_type: Optional[str] = None,
        probe_source: str = "dry_run",
        metadata: Optional[Dict[str, Any]] = None,
        observed_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Record one dry-run provider observation.

        Failure observations append a `policy_dry_run` circuit event. Success
        observations update only aggregate quota-window counters.
        """
        bucket = self._normalize_bucket(result_bucket)
        now = observed_at or datetime.now()
        window_start, window_end = self._window_bounds(now, window_type)
        safe_metadata = self._metadata(metadata, observation_kind="result", result_bucket=bucket)
        duration_bucket_ms = self._duration_bucket_ms(duration_ms)
        is_probe = bool(probe_type) or provider_category == "probe" or route_family == "admin_provider_probe"

        quota_window = self.db.update_provider_quota_window_counters(
            provider=provider,
            provider_category=provider_category,
            route_family=route_family,
            policy_key=policy_key,
            owner_user_id=owner_user_id,
            guest_bucket_hash=guest_bucket_hash,
            window_type=window_type,
            window_start=window_start,
            window_end=window_end,
            request_delta=0 if bucket in self.REJECTED_BUCKETS else 1,
            rejected_delta=1 if bucket in self.REJECTED_BUCKETS else 0,
            success_delta=1 if bucket == "success" else 0,
            failure_delta=1 if bucket in self.FAILURE_BUCKETS else 0,
            timeout_delta=1 if bucket == "timeout" else 0,
            provider_429_delta=1 if bucket == "provider_429" else 0,
            provider_403_delta=1 if bucket == "provider_403" else 0,
            probe_delta=1 if is_probe else 0,
            metadata=safe_metadata,
        )

        event = None
        if bucket in self.FAILURE_BUCKETS:
            event = self.db.append_provider_circuit_event(
                provider=provider,
                event_type="policy_dry_run",
                reason_bucket=bucket,
                provider_category=provider_category,
                route_family=route_family,
                owner_user_id=owner_user_id,
                guest_bucket_hash=guest_bucket_hash,
                duration_bucket_ms=duration_bucket_ms,
                quota_window_start=window_start,
                quota_window_end=window_end,
                metadata=safe_metadata,
                created_at=now,
            )

        probe_event = None
        if is_probe:
            probe_event = self.db.record_provider_probe_event(
                provider=provider,
                provider_category=provider_category,
                route_family=route_family,
                probe_type=probe_type or "synthetic_fixture",
                probe_source=probe_source,
                result_bucket=bucket,
                duration_bucket_ms=duration_bucket_ms,
                metadata=safe_metadata,
                created_at=now,
            )

        return {
            "quota_window": quota_window,
            "event": event,
            "probe_event": probe_event,
            "state": None,
        }

    def record_cooldown_observation(
        self,
        *,
        provider: str,
        reason_bucket: str,
        provider_category: Optional[str] = None,
        route_family: Optional[str] = None,
        owner_user_id: Optional[str] = None,
        guest_bucket_hash: Optional[str] = None,
        cooldown_until: Optional[datetime] = None,
        duration_ms: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        observed_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Record a non-enforcing cooldown observation as an event only."""
        bucket = self._normalize_bucket(reason_bucket)
        if bucket == "success":
            raise ValueError("cooldown observation requires a failure reason bucket")
        now = observed_at or datetime.now()
        safe_metadata = self._metadata(
            metadata,
            observation_kind="cooldown",
            result_bucket=bucket,
            cooldown_until=cooldown_until.isoformat() if cooldown_until else None,
        )
        event = self.db.append_provider_circuit_event(
            provider=provider,
            event_type="policy_dry_run",
            reason_bucket=bucket,
            provider_category=provider_category,
            route_family=route_family,
            owner_user_id=owner_user_id,
            guest_bucket_hash=guest_bucket_hash,
            duration_bucket_ms=self._duration_bucket_ms(duration_ms),
            metadata=safe_metadata,
            created_at=now,
        )
        return {
            "quota_window": None,
            "event": event,
            "probe_event": None,
            "state": None,
        }

    def _normalize_bucket(self, value: str) -> str:
        bucket = str(value or "").strip().lower()
        if bucket not in self.RESULT_BUCKETS:
            raise ValueError("unsupported provider circuit observation bucket")
        return bucket

    @staticmethod
    def _window_bounds(observed_at: datetime, window_type: str) -> Tuple[datetime, datetime]:
        kind = str(window_type or "hour").strip().lower()
        if kind == "minute":
            start = observed_at.replace(second=0, microsecond=0)
            return start, start + timedelta(minutes=1)
        if kind == "day":
            start = observed_at.replace(hour=0, minute=0, second=0, microsecond=0)
            return start, start + timedelta(days=1)
        if kind == "month":
            start = observed_at.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if start.month == 12:
                return start, start.replace(year=start.year + 1, month=1)
            return start, start.replace(month=start.month + 1)
        start = observed_at.replace(minute=0, second=0, microsecond=0)
        return start, start + timedelta(hours=1)

    @staticmethod
    def _duration_bucket_ms(value: Optional[int]) -> Optional[int]:
        if value is None:
            return None
        duration = max(0, int(value or 0))
        for bucket in (50, 100, 250, 500, 1000, 1500, 2000, 5000, 10000, 30000):
            if duration <= bucket:
                return bucket
        return 60000

    @staticmethod
    def _metadata(
        value: Optional[Dict[str, Any]],
        *,
        observation_kind: str,
        result_bucket: str,
        cooldown_until: Optional[str] = None,
    ) -> Dict[str, Any]:
        metadata = dict(value or {})
        metadata.update(
            {
                "dry_run": True,
                "observation_kind": observation_kind,
                "result_bucket": result_bucket,
            }
        )
        if cooldown_until:
            metadata["cooldown_until"] = cooldown_until
        return metadata
