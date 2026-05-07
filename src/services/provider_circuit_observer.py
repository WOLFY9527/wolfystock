# -*- coding: utf-8 -*-
"""Dry-run provider circuit observation helper.

This helper records synthetic provider circuit counters and events only. It does
not read circuit state for enforcement and does not change provider order,
fallback, retry, timeout, or cache behavior.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import desc, select

from src.storage import DatabaseManager, ProviderCircuitEvent, ProviderQuotaWindow


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
    _OPEN_CANDIDATE_BUCKETS = {
        "timeout",
        "provider_5xx",
        "network_error",
        "malformed_payload",
        "insufficient_payload",
    }
    _DEGRADED_STATE_BY_BUCKET = {
        "provider_429": "provider_quota_depleted",
        "quota_policy_block": "provider_quota_depleted",
        "provider_403": "disabled_by_operator",
        "auth_or_key_invalid": "disabled_by_operator",
        "operator_disabled": "disabled_by_operator",
    }

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
            "preflight": self.classify_preflight_state(result_bucket=bucket),
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
            "preflight": self.classify_preflight_state(result_bucket=bucket),
            "state": None,
        }

    def classify_preflight_state(self, *, result_bucket: str) -> Dict[str, Any]:
        """Classify a dry-run observation for future enforcement planning only."""
        bucket = self._normalize_bucket(result_bucket)
        if bucket == "success":
            preflight_state = "healthy"
            state_candidate = "closed"
        elif bucket in self._OPEN_CANDIDATE_BUCKETS:
            preflight_state = "open_candidate"
            state_candidate = "open"
        else:
            preflight_state = "degraded"
            state_candidate = self._DEGRADED_STATE_BY_BUCKET.get(bucket, "degraded_cache_only")

        return {
            "result_bucket": bucket,
            "preflight_state": preflight_state,
            "state_candidate": state_candidate,
            "live_enforcement": False,
            "would_block_call": False,
            "would_change_provider_order": False,
            "would_change_fallback_behavior": False,
        }

    def build_sla_readiness_diagnostics(
        self,
        *,
        provider: str,
        provider_category: Optional[str] = None,
        route_family: Optional[str] = None,
        observed_since: Optional[datetime] = None,
        now: Optional[datetime] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Summarize stored provider observations for launch planning only."""
        safe_limit = max(1, min(int(limit or 50), 200))
        reference_time = now or datetime.now()
        since = observed_since or (reference_time - timedelta(hours=24))
        normalized_provider = self.db._normalize_provider_label(provider)
        normalized_category = self.db._normalize_provider_dimension(provider_category, 64)
        normalized_route = self.db._normalize_provider_dimension(route_family, 64)

        with self.db.get_session() as session:
            window_query = select(ProviderQuotaWindow).where(
                ProviderQuotaWindow.provider == normalized_provider,
                ProviderQuotaWindow.window_end >= since,
            )
            event_query = select(ProviderCircuitEvent).where(
                ProviderCircuitEvent.provider == normalized_provider,
                ProviderCircuitEvent.created_at >= since,
            )
            if normalized_category:
                window_query = window_query.where(ProviderQuotaWindow.provider_category == normalized_category)
                event_query = event_query.where(ProviderCircuitEvent.provider_category == normalized_category)
            if normalized_route:
                window_query = window_query.where(ProviderQuotaWindow.route_family == normalized_route)
                event_query = event_query.where(ProviderCircuitEvent.route_family == normalized_route)

            windows = session.execute(window_query.order_by(desc(ProviderQuotaWindow.window_end)).limit(safe_limit)).scalars().all()
            events = session.execute(event_query.order_by(desc(ProviderCircuitEvent.created_at)).limit(safe_limit)).scalars().all()

            request_count = sum(int(row.request_count or 0) for row in windows)
            failure_count = sum(int(row.failure_count or 0) for row in windows)
            timeout_count = sum(int(row.timeout_count or 0) for row in windows)
            provider_429_count = sum(int(row.provider_429_count or 0) for row in windows)
            provider_403_count = sum(int(row.provider_403_count or 0) for row in windows)
            latest_window_end = max((row.window_end for row in windows if row.window_end), default=None)
            latest_event_at = max((row.created_at for row in events if row.created_at), default=None)
            latest_observation_at = latest_event_at or latest_window_end
            latest_latency_bucket = next(
                (int(row.duration_bucket_ms) for row in events if row.duration_bucket_ms is not None),
                None,
            )
            recent_errors = self._recent_error_summary(events)

        error_rate = (failure_count / request_count) if request_count else None
        freshness_seconds = (
            max(0, int((reference_time - latest_observation_at).total_seconds()))
            if latest_observation_at
            else None
        )
        advisory_bucket = recent_errors[0]["reasonBucket"] if recent_errors else "success"
        preflight = self.classify_preflight_state(result_bucket=advisory_bucket)

        return {
            "provider": normalized_provider,
            "providerCategory": normalized_category,
            "routeFamily": normalized_route,
            "observedSince": since.isoformat(),
            "readOnly": True,
            "noExternalCalls": True,
            "liveEnforcement": False,
            "providerBehaviorChanged": False,
            "marketCacheBehaviorChanged": False,
            "sla": {
                "latencyBucketMs": latest_latency_bucket,
                "latencyState": self._latency_state(latest_latency_bucket),
                "errorRate": round(error_rate, 4) if error_rate is not None else None,
                "errorState": self._error_state(error_rate),
                "freshnessSeconds": freshness_seconds,
                "freshnessState": self._freshness_state(freshness_seconds),
            },
            "counters": {
                "requestCount": request_count,
                "failureCount": failure_count,
                "timeoutCount": timeout_count,
                "provider429Count": provider_429_count,
                "provider403Count": provider_403_count,
            },
            "recentErrors": recent_errors,
            "circuitPreflight": preflight,
        }

    def _normalize_bucket(self, value: str) -> str:
        bucket = str(value or "").strip().lower()
        if bucket not in self.RESULT_BUCKETS:
            raise ValueError("unsupported provider circuit observation bucket")
        return bucket

    def _recent_error_summary(self, events: list[ProviderCircuitEvent]) -> list[Dict[str, Any]]:
        summary: Dict[str, Dict[str, Any]] = {}
        for row in events:
            bucket = str(row.reason_bucket or "").strip().lower()
            if not bucket or bucket == "success" or bucket not in self.FAILURE_BUCKETS:
                continue
            item = summary.setdefault(bucket, {"reasonBucket": bucket, "count": 0, "latestAt": None})
            item["count"] += 1
            created_at = row.created_at.isoformat() if row.created_at else None
            if created_at and (item["latestAt"] is None or created_at > item["latestAt"]):
                item["latestAt"] = created_at
        ordered = sorted(summary.values(), key=lambda item: (item["latestAt"] or "", item["count"]), reverse=True)
        return [
            {
                "reasonBucket": item["reasonBucket"],
                "countBucket": self._count_bucket(int(item["count"])),
                "latestAt": item["latestAt"],
            }
            for item in ordered[:5]
        ]

    @staticmethod
    def _count_bucket(count: int) -> str:
        if count <= 1:
            return "1"
        if count <= 5:
            return "2_5"
        if count <= 20:
            return "6_20"
        return "gt_20"

    @staticmethod
    def _latency_state(latency_bucket_ms: Optional[int]) -> str:
        if latency_bucket_ms is None:
            return "unknown"
        if latency_bucket_ms <= 1000:
            return "normal"
        if latency_bucket_ms <= 5000:
            return "slow"
        return "critical"

    @staticmethod
    def _error_state(error_rate: Optional[float]) -> str:
        if error_rate is None:
            return "unknown"
        if error_rate == 0:
            return "normal"
        if error_rate <= 0.2:
            return "elevated"
        return "critical"

    @staticmethod
    def _freshness_state(freshness_seconds: Optional[int]) -> str:
        if freshness_seconds is None:
            return "unknown"
        if freshness_seconds <= 3600:
            return "fresh"
        if freshness_seconds <= 86400:
            return "stale"
        return "expired"

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
