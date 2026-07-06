# -*- coding: utf-8 -*-
"""Read-only stock evidence for the Decision Desk chat surface."""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional

from src.repositories.analysis_repo import AnalysisRepository
from src.repositories.stock_repo import StockRepository
from src.services.data_source_router import DataSourceRouteRequest, DataSourceRouter
from src.services.sec_edgar_evidence_service import (
    SEC_EDGAR_FRESHNESS_EXPECTATION,
    SEC_EDGAR_PROVIDER_ID,
    SEC_EDGAR_PROVIDER_NAME,
    SEC_EDGAR_SOURCE_TIER,
    SEC_EDGAR_TRUST_LEVEL,
    SecEdgarFilingEvidenceSidecar,
    build_sec_filing_evidence_sidecar,
)
from src.services.stock_evidence_packet import project_stock_evidence_packet
from src.services.product_read_model import build_stock_evidence_product_read_model
from src.services.stock_evidence_quote_adapter import (
    StockEvidenceQuoteAdapter,
    build_quote_diagnostic_source_metadata,
)
from src.services.symbol_evidence_readiness import build_symbol_evidence_readiness


EvidencePayload = Dict[str, Any]
logger = logging.getLogger(__name__)
_SEC_STOCK_EVIDENCE_USE_CASE = "stock_evidence"
_SEC_ALLOWED_EVIDENCE_CAPABILITIES = frozenset({"companyfacts", "filing"})
_SEC_AUTHORITY_REJECTION_TOKENS = ("quote", "ohlcv", "score", "scoring", "fundamental_authority")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _number(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        number = float(str(value).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _compact_number(value: Any) -> Optional[float]:
    number = _number(value)
    if number is None:
        return None
    return round(number, 4)


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _normalize_symbol(symbol: str) -> str:
    return str(symbol or "").strip().upper().replace(".HK", "").removeprefix("HK")


def _infer_market(symbol: str) -> str:
    normalized = str(symbol or "").strip().upper()
    if normalized.endswith(".HK") or (normalized.startswith("HK") and normalized[2:].isdigit()):
        return "HK"
    if normalized.isdigit() and len(normalized) in {4, 5}:
        return "HK"
    if normalized.isdigit() and len(normalized) == 6:
        return "CN"
    if normalized:
        return "US"
    return "unknown"


def _moving_average(values: List[float], window: int) -> Optional[float]:
    if len(values) < window:
        return None
    return round(sum(values[-window:]) / window, 4)


def _rsi(values: List[float], window: int = 14) -> Optional[float]:
    if len(values) <= window:
        return None
    gains: List[float] = []
    losses: List[float] = []
    recent = values[-(window + 1):]
    for previous, current in zip(recent, recent[1:]):
        delta = current - previous
        if delta >= 0:
            gains.append(delta)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(delta))
    avg_gain = sum(gains) / window
    avg_loss = sum(losses) / window
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else None
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 4)


def _safe_json(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _nested(payload: Any, *path: str) -> Any:
    current = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _first_compact_number(*values: Any) -> Optional[float]:
    for value in values:
        number = _compact_number(value)
        if number is not None:
            return number
    return None


def _find_field(fields: Any, aliases: Iterable[str]) -> Optional[float]:
    alias_set = {alias.lower() for alias in aliases}
    if not isinstance(fields, list):
        return None
    for item in fields:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").lower()
        if any(alias in label for alias in alias_set):
            value = _compact_number(item.get("rawValue") or item.get("value"))
            if value is not None:
                return value
    return None


def _compact_or_find_field(fields: Any, aliases: Iterable[str], *values: Any) -> Optional[float]:
    number = _first_compact_number(*values)
    if number is not None:
        return number
    return _find_field(fields, aliases)


def _fundamental_period(field_periods: Any) -> Optional[str]:
    if not isinstance(field_periods, Mapping):
        return None
    values = []
    for key in (
        "marketCap",
        "trailingPE",
        "priceToBook",
        "beta",
        "totalRevenue",
        "netIncome",
        "freeCashflow",
        "grossMargins",
        "operatingMargins",
        "returnOnEquity",
        "returnOnAssets",
    ):
        value = _text(field_periods.get(key)).lower()
        if value and value not in values:
            values.append(value)
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    return "mixed"


def _normalize_sec_filing_evidence_by_symbol(
    sec_filing_evidence_by_symbol: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    if not sec_filing_evidence_by_symbol:
        return {}
    normalized: Dict[str, Any] = {}
    for symbol, injected in sec_filing_evidence_by_symbol.items():
        normalized_symbol = _normalize_symbol(symbol)
        if not normalized_symbol or normalized_symbol in normalized:
            continue
        normalized[normalized_symbol] = injected
    return normalized


def _serialize_sec_filing_evidence(injected: Any) -> Optional[EvidencePayload]:
    if injected is None:
        return None
    if isinstance(injected, SecEdgarFilingEvidenceSidecar):
        return injected.to_dict()
    return build_sec_filing_evidence_sidecar(injected).to_dict()


def _reject_sec_filing_evidence(reason: str) -> EvidencePayload:
    return {
        "status": "rejected",
        "providerName": SEC_EDGAR_PROVIDER_NAME,
        "providerId": SEC_EDGAR_PROVIDER_ID,
        "sourceTier": SEC_EDGAR_SOURCE_TIER,
        "trustLevel": SEC_EDGAR_TRUST_LEVEL,
        "freshnessExpectation": SEC_EDGAR_FRESHNESS_EXPECTATION,
        "observationOnly": True,
        "scoreContributionAllowed": False,
        "rawPayloadStored": False,
        "records": [],
        "degradationReason": reason,
    }


def _sec_record_capability(record_payload: Mapping[str, Any]) -> str | None:
    evidence_type = str(record_payload.get("evidenceType") or "").strip().lower()
    if not evidence_type:
        return None
    if any(token in evidence_type for token in _SEC_AUTHORITY_REJECTION_TOKENS):
        return None
    if "filing" in evidence_type:
        return "filing"
    if "company_fact" in evidence_type or "companyfacts" in evidence_type:
        return "companyfacts"
    return None


def _sec_route_is_allowed(
    *,
    symbol: str,
    capability: str,
    route_plan: Any,
) -> bool:
    if _infer_market(symbol) != "US":
        return False
    if capability not in _SEC_ALLOWED_EVIDENCE_CAPABILITIES:
        return False
    primary_ids = {str(getattr(candidate, "provider_id", "")).strip().lower() for candidate in route_plan.primary_candidates}
    if primary_ids != {SEC_EDGAR_PROVIDER_ID}:
        return False
    if route_plan.observation_candidates:
        return False
    if route_plan.score_contribution_allowed:
        return False
    return True


def _guard_sec_filing_evidence(symbol: str, injected: Any) -> Optional[EvidencePayload]:
    payload = _serialize_sec_filing_evidence(injected)
    if payload is None:
        return None
    if str(payload.get("providerId") or "").strip().lower() != SEC_EDGAR_PROVIDER_ID:
        return _reject_sec_filing_evidence("sec_provider_mismatch")
    if payload.get("sourceTier") != SEC_EDGAR_SOURCE_TIER:
        return _reject_sec_filing_evidence("sec_source_tier_not_official_public")
    if payload.get("observationOnly") is not True:
        return _reject_sec_filing_evidence("sec_sidecar_authority_not_allowed")
    if payload.get("scoreContributionAllowed") is not False:
        return _reject_sec_filing_evidence("sec_sidecar_authority_not_allowed")
    if payload.get("rawPayloadStored") is not False:
        return _reject_sec_filing_evidence("sec_raw_payload_not_allowed")

    record_payloads = payload.get("records")
    if not isinstance(record_payloads, list):
        return _reject_sec_filing_evidence("sec_records_payload_invalid")

    capabilities = {
        capability
        for capability in (
            _sec_record_capability(record_payload)
            for record_payload in record_payloads
            if isinstance(record_payload, Mapping)
        )
        if capability is not None
    }
    if len(capabilities) > 1:
        return _reject_sec_filing_evidence("sec_mixed_evidence_capabilities_not_allowed")
    if record_payloads and not capabilities:
        return _reject_sec_filing_evidence("sec_sidecar_authority_not_allowed")

    capability = next(iter(capabilities), "companyfacts")
    route_plan = DataSourceRouter.resolve(
        DataSourceRouteRequest(
            market=_infer_market(symbol),
            asset_type="stock",
            use_case=_SEC_STOCK_EVIDENCE_USE_CASE,
            capability=capability,
            freshness_need="daily",
            scoring_allowed=False,
            symbol=symbol,
            allow_network=False,
            reproducibility_required=False,
        )
    )
    if not _sec_route_is_allowed(symbol=symbol, capability=capability, route_plan=route_plan):
        return _reject_sec_filing_evidence("sec_stock_evidence_route_not_allowed")
    return payload


class StockEvidenceService:
    """Build a small, read-only evidence payload without scanner/backtest/LLM execution."""

    def __init__(
        self,
        *,
        fetcher_manager: Optional[Any] = None,
        stock_repo: Optional[StockRepository] = None,
        analysis_repo: Optional[AnalysisRepository] = None,
        owner_id: Optional[str] = None,
    ) -> None:
        self.quote_adapter = StockEvidenceQuoteAdapter(fetcher_manager=fetcher_manager)
        self.fetcher_manager = self.quote_adapter.fetcher_manager
        self.stock_repo = stock_repo or StockRepository()
        self.analysis_repo = analysis_repo or AnalysisRepository(owner_id=owner_id)

    def get_stock_evidence(
        self,
        symbols: List[str],
        *,
        sec_filing_evidence_by_symbol: Mapping[str, Any] | None = None,
    ) -> EvidencePayload:
        normalized = []
        for symbol in symbols[:3]:
            value = _normalize_symbol(symbol)
            if value and value not in normalized:
                normalized.append(value)
        normalized_sec_filing_evidence = _normalize_sec_filing_evidence_by_symbol(
            sec_filing_evidence_by_symbol
        )
        payload = {
            "symbols": normalized,
            "items": [
                self._build_item(
                    symbol,
                    sec_filing_evidence=normalized_sec_filing_evidence.get(symbol),
                )
                for symbol in normalized
            ],
            "meta": {"generatedAt": _now_iso(), "source": "read_only_evidence_v2"},
        }
        self._attach_stock_evidence_packets(payload)
        self._attach_symbol_evidence_readiness(payload)
        self._attach_product_read_models(payload)
        return payload

    def _attach_stock_evidence_packets(self, payload: EvidencePayload) -> None:
        meta = payload.get("meta") if isinstance(payload.get("meta"), Mapping) else {}
        items = payload.get("items")
        if not isinstance(items, list):
            return
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                item["stockEvidencePacket"] = project_stock_evidence_packet(
                    {"items": [item], "meta": meta}
                )
            except Exception as exc:
                logger.warning(
                    "Stock evidence packet projection failed for %s: %s",
                    item.get("symbol") or "unknown",
                    exc,
                    exc_info=True,
                )

    def _attach_symbol_evidence_readiness(self, payload: EvidencePayload) -> None:
        items = payload.get("items")
        if not isinstance(items, list):
            return
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                item["symbolEvidenceReadiness"] = build_symbol_evidence_readiness(item)
            except Exception as exc:
                logger.warning(
                    "Symbol evidence readiness projection failed for %s: %s",
                    item.get("symbol") or "unknown",
                    exc,
                    exc_info=True,
                )

    def _attach_product_read_models(self, payload: EvidencePayload) -> None:
        items = payload.get("items")
        if not isinstance(items, list):
            return
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                item["productReadModel"] = build_stock_evidence_product_read_model(item)
            except Exception as exc:
                logger.warning(
                    "Stock evidence product read model projection failed for %s: %s",
                    item.get("symbol") or "unknown",
                    exc,
                    exc_info=True,
                )

    def _build_item(
        self,
        symbol: str,
        *,
        sec_filing_evidence: Any = None,
    ) -> EvidencePayload:
        quote = self._quote(symbol)
        item = {
            "symbol": symbol,
            "market": _infer_market(symbol),
            "quote": quote,
            "technical": self._technical(symbol),
            "fundamental": self._fundamental(symbol, quote_payload=quote),
            "news": {"status": "unknown", "latestHeadline": None, "provider": None},
        }
        sec_filing_evidence_payload = _guard_sec_filing_evidence(symbol, sec_filing_evidence)
        if sec_filing_evidence_payload is not None:
            item["secFilingEvidence"] = sec_filing_evidence_payload
        return item

    def _quote(self, symbol: str) -> EvidencePayload:
        try:
            quote = self.quote_adapter.get_quote_snapshot(symbol)
        except Exception as exc:
            return {
                "status": "error",
                "provider": "realtime_quote",
                "error": str(exc)[:120],
                **build_quote_diagnostic_source_metadata(
                    source="realtime_quote",
                    as_of=None,
                    is_unavailable=True,
                ),
            }
        if quote is None:
            return {
                "status": "unknown",
                "provider": "realtime_quote",
                **build_quote_diagnostic_source_metadata(
                    source="realtime_quote",
                    as_of=None,
                    is_unavailable=True,
                ),
            }
        payload: EvidencePayload = {
            "status": "available",
            "price": _compact_number(quote.price),
            "changePct": _compact_number(quote.change_pct),
            "currency": "USD" if _infer_market(symbol) == "US" else "CNY" if _infer_market(symbol) == "CN" else "HKD",
            "provider": quote.source or "realtime_quote",
            "updatedAt": quote.market_timestamp,
            **quote.source_metadata,
        }
        for target, attr in (
            ("marketCap", "total_mv"),
            ("peTtm", "pe_ratio"),
            ("pb", "pb_ratio"),
        ):
            value = _compact_number(getattr(quote, attr, None))
            if value is not None:
                payload[target] = value
        return payload

    def _technical(self, symbol: str) -> EvidencePayload:
        try:
            rows = list(self.stock_repo.get_recent_daily_rows(code=symbol, limit=80))
        except Exception as exc:
            return {"status": "error", "provider": "stock_daily", "error": str(exc)[:120]}
        if not rows:
            return {"status": "missing", "provider": "stock_daily"}
        rows_asc = list(reversed(rows))
        closes = [_number(getattr(row, "close", None)) for row in rows_asc]
        closes = [value for value in closes if value is not None]
        latest = rows[0]
        latest_close = _compact_number(getattr(latest, "close", None))
        ma5 = _compact_number(getattr(latest, "ma5", None)) or _moving_average(closes, 5)
        ma10 = _compact_number(getattr(latest, "ma10", None)) or _moving_average(closes, 10)
        ma20 = _compact_number(getattr(latest, "ma20", None)) or _moving_average(closes, 20)
        ma60 = _moving_average(closes, 60)
        lows = [_number(getattr(row, "low", None)) for row in rows[:20]]
        highs = [_number(getattr(row, "high", None)) for row in rows[:20]]
        support = min([value for value in lows if value is not None], default=None)
        resistance = max([value for value in highs if value is not None], default=None)
        trend = "unknown"
        if latest_close is not None and ma20 is not None:
            trend = "bullish" if latest_close >= ma20 else "bearish"
        payload: EvidencePayload = {
            "status": "available" if any(value is not None for value in [ma5, ma10, ma20, ma60, support, resistance]) else "missing",
            "trend": trend,
            "ma5": ma5,
            "ma10": ma10,
            "ma20": ma20,
            "ma60": ma60,
            "rsi14": _rsi(closes, 14),
            "support": _compact_number(support),
            "resistance": _compact_number(resistance),
            "provider": "stock_daily",
            "updatedAt": str(getattr(latest, "date", "") or ""),
        }
        if payload["status"] == "available" and any(payload.get(key) is None for key in ["ma20", "rsi14", "support", "resistance"]):
            payload["status"] = "partial"
        return payload

    def _fundamental(self, symbol: str, *, quote_payload: Optional[EvidencePayload] = None) -> EvidencePayload:
        try:
            record = self.analysis_repo.get_latest_record(code=symbol)
        except Exception as exc:
            return {"status": "error", "provider": "analysis_history", "error": str(exc)[:120]}
        if record is None:
            return self._fundamental_from_quote(quote_payload or {})

        raw = _safe_json(getattr(record, "raw_result", None))
        snapshot = _safe_json(getattr(record, "context_snapshot", None))
        standard = (
            _nested(raw, "details", "standard_report")
            or raw.get("standard_report")
            or _nested(snapshot, "standard_report")
            or {}
        )
        fields = _nested(standard, "table_sections", "fundamental", "fields") or standard.get("fundamental_fields")
        normalized = (
            _nested(raw, "dashboard", "structured_analysis", "fundamentals", "normalized")
            or _nested(snapshot, "enhanced_context", "fundamentals", "normalized")
            or {}
        )
        field_periods = (
            _nested(raw, "dashboard", "structured_analysis", "fundamentals", "field_periods")
            or _nested(snapshot, "enhanced_context", "fundamentals", "field_periods")
            or {}
        )

        payload: EvidencePayload = {
            "status": "missing",
            "marketCap": _compact_number(normalized.get("marketCap")) or _find_field(fields, ["market cap", "总市值"]),
            "peTtm": _compact_number(normalized.get("trailingPE")) or _find_field(fields, ["pe", "市盈率"]),
            "pb": _compact_number(normalized.get("priceToBook")) or _find_field(fields, ["price to book", "市净率"]),
            "beta": _compact_number(normalized.get("beta")) or _find_field(fields, ["beta"]),
            "revenueTtm": _compact_number(normalized.get("totalRevenue")) or _find_field(fields, ["revenue", "营收"]),
            "netIncomeTtm": _compact_number(normalized.get("netIncome")) or _find_field(fields, ["net income", "净利润"]),
            "fcfTtm": _compact_number(normalized.get("freeCashflow")) or _find_field(fields, ["free cash flow", "自由现金流"]),
            "grossMargin": _compact_or_find_field(
                fields,
                ["gross margin", "毛利率"],
                normalized.get("grossMargins"),
                normalized.get("grossMargin"),
            ),
            "operatingMargin": _compact_or_find_field(
                fields,
                ["operating margin", "营业利润率"],
                normalized.get("operatingMargins"),
                normalized.get("operatingMargin"),
            ),
            "roe": _compact_or_find_field(
                fields,
                ["roe"],
                normalized.get("returnOnEquity"),
                normalized.get("roe"),
            ),
            "roa": _compact_or_find_field(
                fields,
                ["roa"],
                normalized.get("returnOnAssets"),
                normalized.get("roa"),
            ),
            "period": _fundamental_period(field_periods),
            "provider": "analysis_history",
            "updatedAt": getattr(getattr(record, "created_at", None), "isoformat", lambda: None)(),
        }
        self._finalize_fundamental(payload)
        if payload["status"] == "missing":
            return self._fundamental_from_quote(quote_payload or {})
        return payload

    def _fundamental_from_quote(self, quote: EvidencePayload) -> EvidencePayload:
        payload: EvidencePayload = {
            "status": "missing",
            "marketCap": quote.get("marketCap"),
            "peTtm": quote.get("peTtm"),
            "pb": quote.get("pb"),
            "beta": None,
            "revenueTtm": None,
            "netIncomeTtm": None,
            "fcfTtm": None,
            "provider": quote.get("provider") or "realtime_quote",
            "updatedAt": quote.get("updatedAt"),
        }
        self._finalize_fundamental(payload)
        return payload

    def _finalize_fundamental(self, payload: EvidencePayload) -> None:
        required = ["marketCap", "peTtm", "pb", "beta", "revenueTtm", "netIncomeTtm", "fcfTtm"]
        missing = [key for key in required if payload.get(key) is None]
        payload["missingFields"] = missing
        present_count = len(required) - len(missing)
        if present_count == len(required):
            payload["status"] = "available"
        elif present_count > 0:
            payload["status"] = "partial"
        else:
            payload["status"] = "missing"
