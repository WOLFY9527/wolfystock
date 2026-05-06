# -*- coding: utf-8 -*-
"""Safe local import helpers for LLM model pricing policies."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import select

from src.storage import DatabaseManager, ModelPricingPolicy
from src.utils.security import sanitize_message, sanitize_url


@dataclass(frozen=True)
class PricingPolicyImportItem:
    status: str
    reason_code: Optional[str] = None
    policy_key: Optional[str] = None


@dataclass(frozen=True)
class PricingPolicyImportSummary:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    rejected: int = 0
    items: List[PricingPolicyImportItem] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
            "rejected": self.rejected,
            "items": [item.__dict__ for item in self.items],
        }


class ModelPricingPolicyImportService:
    """Validate and upsert local pricing policy records without network access."""

    SAFE_REJECTION_REASON_CODES = {
        "invalid_record",
        "missing_provider",
        "missing_model",
        "missing_effective_from",
        "invalid_effective_date",
        "negative_price",
        "invalid_price",
        "invalid_source_url",
    }

    def __init__(self, *, db: Optional[DatabaseManager] = None) -> None:
        self.db = db or DatabaseManager.get_instance()

    def import_records(
        self,
        records: Iterable[Dict[str, Any]],
        *,
        deactivate_superseded: bool = False,
    ) -> PricingPolicyImportSummary:
        created = updated = skipped = rejected = 0
        items: List[PricingPolicyImportItem] = []

        for raw in records:
            normalized, reason = self._normalize_record(raw)
            if reason is not None:
                rejected += 1
                items.append(PricingPolicyImportItem(status="rejected", reason_code=reason))
                continue

            assert normalized is not None
            existing = self._find_existing_policy(normalized)
            policy_key = existing.policy_key if existing is not None else normalized.get("policy_key")
            if not policy_key:
                policy_key = self._build_policy_key(normalized)
            normalized["policy_key"] = policy_key

            if existing is not None and self._matches_existing(existing, normalized):
                skipped += 1
                items.append(PricingPolicyImportItem(status="skipped", policy_key=policy_key))
                continue

            self.db.upsert_model_pricing_policy(**normalized)
            if deactivate_superseded and normalized.get("active"):
                self._deactivate_superseded(normalized)

            if existing is None:
                created += 1
                status = "created"
            else:
                updated += 1
                status = "updated"
            items.append(PricingPolicyImportItem(status=status, policy_key=policy_key))

        return PricingPolicyImportSummary(
            created=created,
            updated=updated,
            skipped=skipped,
            rejected=rejected,
            items=items,
        )

    def import_file(self, path: str | Path, *, deactivate_superseded: bool = False) -> PricingPolicyImportSummary:
        """Load local JSON records and import them. This function performs no HTTP requests."""
        with Path(path).open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        records = payload.get("policies") if isinstance(payload, dict) else payload
        if not isinstance(records, list):
            return PricingPolicyImportSummary(
                rejected=1,
                items=[PricingPolicyImportItem(status="rejected", reason_code="invalid_record")],
            )
        return self.import_records(records, deactivate_superseded=deactivate_superseded)

    def _normalize_record(self, record: Any) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        if not isinstance(record, dict):
            return None, "invalid_record"

        provider = self._normalize_label(record.get("provider"), limit=64)
        model = self._normalize_label(record.get("model"), limit=128)
        if not provider:
            return None, "missing_provider"
        if not model:
            return None, "missing_model"
        if not record.get("effective_from"):
            return None, "missing_effective_from"

        effective_from = self._parse_datetime(record.get("effective_from"))
        effective_until = self._parse_datetime(record.get("effective_until")) if record.get("effective_until") else None
        if effective_from is None or (record.get("effective_until") and effective_until is None):
            return None, "invalid_effective_date"

        input_price, reason = self._parse_price(record.get("input_price_per_1m", 0), required=True)
        if reason:
            return None, reason
        cached_price, reason = self._parse_price(record.get("cached_input_price_per_1m"), required=False)
        if reason:
            return None, reason
        output_price, reason = self._parse_price(record.get("output_price_per_1m", 0), required=True)
        if reason:
            return None, reason

        source_url = self._normalize_source_url(record.get("source_url"))
        if source_url is False:
            return None, "invalid_source_url"

        metadata = record.get("metadata", record.get("notes", {}))
        if isinstance(record.get("notes"), str):
            metadata = {"notes": record.get("notes"), **(metadata if isinstance(metadata, dict) else {})}
        currency = self._normalize_label(record.get("currency") or "USD", limit=8, lowercase=False) or "USD"

        return {
            "policy_key": self._normalize_label(record.get("policy_key"), limit=160, lowercase=False),
            "provider": provider,
            "model": model,
            "pricing_unit": "per_1m_tokens",
            "input_price_per_1m": input_price,
            "cached_input_price_per_1m": cached_price,
            "output_price_per_1m": output_price,
            "currency": currency.upper(),
            "effective_from": effective_from,
            "effective_until": effective_until,
            "source_label": sanitize_message(str(record.get("source_label") or "").strip())[:128] or None,
            "source_url": source_url or None,
            "active": bool(record.get("active", True)),
            "metadata": self.db._sanitize_llm_cost_metadata(metadata if isinstance(metadata, dict) else {}),
        }, None

    def _find_existing_policy(self, normalized: Dict[str, Any]) -> Optional[ModelPricingPolicy]:
        policy_key = normalized.get("policy_key")
        with self.db.get_session() as session:
            row = None
            if policy_key:
                row = session.execute(
                    select(ModelPricingPolicy)
                    .where(ModelPricingPolicy.policy_key == policy_key)
                    .limit(1)
                ).scalar_one_or_none()
            if row is None:
                row = session.execute(
                    select(ModelPricingPolicy)
                    .where(
                        ModelPricingPolicy.provider == normalized["provider"],
                        ModelPricingPolicy.model == normalized["model"],
                        ModelPricingPolicy.effective_from == normalized["effective_from"],
                    )
                    .limit(1)
                ).scalar_one_or_none()
            if row is not None:
                session.expunge(row)
            return row

    def _deactivate_superseded(self, normalized: Dict[str, Any]) -> None:
        with self.db.session_scope() as session:
            rows = session.execute(
                select(ModelPricingPolicy).where(
                    ModelPricingPolicy.provider == normalized["provider"],
                    ModelPricingPolicy.model == normalized["model"],
                    ModelPricingPolicy.policy_key != normalized["policy_key"],
                    ModelPricingPolicy.effective_from < normalized["effective_from"],
                    ModelPricingPolicy.active.is_(True),
                )
            ).scalars().all()
            for row in rows:
                row.active = False
                if row.effective_until is None or row.effective_until > normalized["effective_from"]:
                    row.effective_until = normalized["effective_from"]
                row.updated_at = datetime.now()

    def _matches_existing(self, row: ModelPricingPolicy, normalized: Dict[str, Any]) -> bool:
        existing = row.to_dict()
        return all(
            [
                existing.get("provider") == normalized.get("provider"),
                existing.get("model") == normalized.get("model"),
                existing.get("pricing_unit") == normalized.get("pricing_unit"),
                existing.get("input_price_per_1m") == self._decimal_text(normalized.get("input_price_per_1m")),
                existing.get("cached_input_price_per_1m") == self._decimal_text(normalized.get("cached_input_price_per_1m")),
                existing.get("output_price_per_1m") == self._decimal_text(normalized.get("output_price_per_1m")),
                existing.get("currency") == normalized.get("currency"),
                existing.get("effective_from") == normalized.get("effective_from").isoformat(),
                existing.get("effective_until") == (
                    normalized.get("effective_until").isoformat() if normalized.get("effective_until") else None
                ),
                existing.get("source_label") == normalized.get("source_label"),
                existing.get("source_url") == normalized.get("source_url"),
                bool(existing.get("active")) == bool(normalized.get("active")),
                existing.get("metadata") == normalized.get("metadata"),
            ]
        )

    @staticmethod
    def _normalize_label(value: Any, *, limit: int, lowercase: bool = True) -> Optional[str]:
        text = sanitize_message(str(value or "").strip())
        if lowercase:
            text = text.lower()
        return text[:limit] or None

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            parsed = value
        else:
            try:
                text = str(value or "").strip().replace("Z", "+00:00")
                parsed = datetime.fromisoformat(text)
            except (TypeError, ValueError):
                return None
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed

    @staticmethod
    def _parse_price(value: Any, *, required: bool) -> Tuple[Optional[Decimal], Optional[str]]:
        if value in (None, "") and not required:
            return None, None
        try:
            price = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return None, "invalid_price"
        if price < 0:
            return None, "negative_price"
        return price, None

    @staticmethod
    def _decimal_text(value: Any) -> Optional[str]:
        if value is None:
            return None
        return str(Decimal(str(value)).quantize(Decimal("0.00000001")))

    @staticmethod
    def _normalize_source_url(value: Any) -> Optional[str] | bool:
        text = str(value or "").strip()
        if not text:
            return None
        sanitized = sanitize_url(text)
        if sanitized != text:
            return False
        lowered = text.lower()
        if not (lowered.startswith("https://") or lowered.startswith("http://")):
            return False
        return sanitize_message(text)[:500]

    @staticmethod
    def _build_policy_key(normalized: Dict[str, Any]) -> str:
        stamp = normalized["effective_from"].strftime("%Y%m%d%H%M%S")
        raw = f"{normalized['provider']}:{normalized['model']}:{stamp}"
        return sanitize_message(raw)[:160]
