# -*- coding: utf-8 -*-
"""
===================================
股票数据接口
===================================

职责：
1. POST /api/v1/stocks/extract-from-image 从图片提取股票代码
2. POST /api/v1/stocks/parse-import 解析 CSV/Excel/剪贴板
3. GET /api/v1/stocks/{code}/quote 实时行情接口
4. GET /api/v1/stocks/{code}/history 历史行情接口
"""

import logging
from collections.abc import Mapping
from typing import Any, Optional

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile

from api.v1.consumer_safe_response import consumer_safe_json_response
from api.v1.schemas.stocks import (
    ExtractFromImageResponse,
    ExtractItem,
    IntradayBar,
    StockStructureDecisionBatchRequest,
    StockStructureDecisionBatchResponse,
    KLineData,
    StockStructureDecisionResponse,
    StockEvidenceResponse,
    StockHistoryResponse,
    StockIntradayResponse,
    StockQuote,
    SymbolResearchPacketResponse,
    StockValidationResponse,
)
from api.v1.schemas.common import ErrorResponse
from src.services.image_stock_extractor import (
    ALLOWED_MIME,
    MAX_SIZE_BYTES,
    extract_stock_codes_from_image,
)
from src.services.import_parser import (
    MAX_FILE_BYTES,
    parse_import_from_bytes,
    parse_import_from_text,
)
from src.services.agent_stock_evidence_service import StockEvidenceService
from src.services.stock_service import StockService
from src.services.stock_structure_decision_service import StockStructureDecisionService
from src.utils.symbol_validation import (
    ConsumerSymbolPrecheck,
    validate_consumer_symbol_precheck,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# 须在 /{stock_code} 路由之前定义
ALLOWED_MIME_STR = ", ".join(ALLOWED_MIME)
_VALIDATION_UNAVAILABLE_MESSAGE = "Symbol validation is temporarily unavailable. Try again later."
_VALIDATION_VERIFIED_MESSAGE = "Symbol verified."
_VALIDATION_UNKNOWN_MESSAGE = "Symbol format is supported, but verification is not confirmed yet."
_RESEARCH_PACKET_NO_ADVICE_DISCLOSURE = "Observation-only research packet; no personalized action instruction."
_RESEARCH_PACKET_HISTORY_DAYS = 90


class _ReadOnlyEvidenceFetcherManager:
    """Fail-closed quote seam for the API contract endpoint."""

    def get_realtime_quote(self, symbol: str):
        return None


def _stock_validation_response(
    precheck: ConsumerSymbolPrecheck,
    *,
    status: str | None = None,
    valid: bool = False,
    exists: bool = False,
    stock_name: Optional[str] = None,
    message: str | None = None,
) -> StockValidationResponse:
    normalized_symbol = precheck.normalized_symbol or precheck.raw_symbol
    return StockValidationResponse(
        stock_code=normalized_symbol,
        normalized_symbol=normalized_symbol,
        market=precheck.market,
        status=status or precheck.status,
        valid=valid,
        exists=exists,
        stock_name=_consumer_safe_stock_name(stock_name, normalized_symbol),
        message=message or precheck.message,
    )


def _consumer_safe_stock_name(value: object, symbol: str) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    if text.upper() == str(symbol or "").strip().upper():
        return None
    if any(
        marker in text.lower()
        for marker in (
            "traceback",
            "http://",
            "https://",
            "api_key",
            "apikey",
            "secret",
            "cookie",
            "session",
            "token",
            "trustlevel",
            "reasoncode",
            "sourcetype",
            "fallback",
        )
    ):
        return None
    return text


def _get_nested(payload: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _as_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _is_true(payload: Mapping[str, Any], *keys: str) -> bool:
    return any(bool(_get_nested(payload, key)) for key in keys)


def _quote_packet(quote: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = _as_mapping(quote)
    price = _safe_float(_get_nested(payload, "current_price", "currentPrice", "price"))
    change_percent = _safe_float(_get_nested(payload, "change_percent", "changePercent"))
    market_timestamp = _safe_text(_get_nested(payload, "market_timestamp", "marketTimestamp"))
    observed_at = _safe_text(_get_nested(payload, "observed_at", "observedAt", "update_time", "updateTime"))
    freshness = str(_get_nested(payload, "freshness") or "").strip().lower()

    state = "missing"
    as_of = None
    if payload and price is not None and price > 0 and not _is_true(payload, "is_synthetic", "isSynthetic"):
        degraded = (
            _is_true(payload, "is_fallback", "isFallback", "is_stale", "isStale", "is_partial", "isPartial")
            or freshness in {"fallback", "stale", "synthetic", "unavailable", "cached", "delayed"}
            or not market_timestamp
        )
        state = "stale" if degraded else "available"
        as_of = market_timestamp or observed_at

    return {
        "state": state,
        "price": price if state in {"available", "stale"} else None,
        "changePercent": change_percent if state in {"available", "stale"} else None,
        "asOf": as_of,
    }


def _history_packet(history: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = _as_mapping(history)
    rows = _as_list(payload.get("data"))
    period = _safe_text(payload.get("period")) or "daily"
    latest_row = _as_mapping(rows[-1]) if rows else {}
    diagnostics = _as_mapping(payload.get("diagnostics"))
    source_confidence = _as_mapping(_get_nested(payload, "sourceConfidence", "source_confidence"))
    diagnostic_status = str(diagnostics.get("status") or "").strip().lower()
    source = str(payload.get("source") or "").strip().lower()
    freshness = str(source_confidence.get("freshness") or "").strip().lower()

    state = "missing"
    if rows:
        unavailable = (
            source == "unavailable"
            or diagnostic_status == "unavailable"
            or _is_true(source_confidence, "isUnavailable", "is_unavailable", "isSynthetic", "is_synthetic")
            or freshness in {"unavailable", "synthetic"}
        )
        degraded = (
            diagnostic_status in {"degraded", "partial", "stale"}
            or _is_true(source_confidence, "isFallback", "is_fallback", "isStale", "is_stale", "isPartial", "is_partial")
            or freshness in {"fallback", "stale", "cached", "delayed", "partial"}
        )
        state = "missing" if unavailable else ("stale" if degraded else "available")

    return {
        "state": state,
        "bars": len(rows),
        "period": period,
        "asOf": _safe_text(latest_row.get("date")) if rows else None,
    }


def _structure_packet(structure: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = _as_mapping(structure)
    data_quality = _as_mapping(_get_nested(payload, "dataQuality", "data_quality"))
    quality_status = str(data_quality.get("status") or "").strip().lower()
    if quality_status == "available":
        state = "available"
    elif quality_status in {"partial", "insufficient"}:
        state = "insufficient"
    elif quality_status == "unavailable":
        state = "missing"
    else:
        state = "unknown" if payload else "missing"

    return {
        "state": state,
        "label": _safe_text(_get_nested(payload, "structureState", "structure_state")) if state in {"available", "insufficient"} else None,
        "confidence": _safe_text(payload.get("confidence")) if state in {"available", "insufficient"} else None,
        "asOf": None,
    }


def _first_evidence_item(evidence: Mapping[str, Any] | None, symbol: str) -> dict[str, Any] | None:
    items = _as_list(_as_mapping(evidence).get("items"))
    for item in items:
        item_payload = _as_mapping(item)
        if str(item_payload.get("symbol") or "").strip().upper() == symbol.upper():
            return item_payload
    return _as_mapping(items[0]) if items else None


def _fundamentals_packet(item: Mapping[str, Any] | None) -> dict[str, Any]:
    if item is None:
        return {"state": "not_integrated", "fieldsAvailable": []}

    fundamental = _as_mapping(item.get("fundamental"))
    packet = _as_mapping(_get_nested(item, "stockEvidencePacket", "stock_evidence_packet"))
    summary = _as_mapping(_get_nested(packet, "fundamentalsSummary", "fundamentals_summary"))
    allowed_fields = (
        "marketCap",
        "peTtm",
        "pb",
        "beta",
        "revenueTtm",
        "netIncomeTtm",
        "fcfTtm",
        "grossMargin",
        "operatingMargin",
        "roe",
        "roa",
    )
    fields_available = [field for field in allowed_fields if summary.get(field) is not None]
    status = str(summary.get("status") or fundamental.get("status") or "").strip().lower()

    if fields_available:
        state = "available"
    elif not fundamental and not summary:
        state = "not_integrated"
    elif status in {"missing", "unavailable", "no_evidence", "insufficient"}:
        state = "missing"
    else:
        state = "unknown"
    return {"state": state, "fieldsAvailable": fields_available}


def _events_packet(item: Mapping[str, Any] | None) -> dict[str, Any]:
    if item is None:
        return {"state": "not_integrated", "latest": []}

    news = _as_mapping(item.get("news"))
    filing = _as_mapping(_get_nested(item, "secFilingEvidence", "sec_filing_evidence"))
    latest: list[dict[str, Any]] = []

    for record in _as_list(news.get("latest")):
        record_payload = _as_mapping(record)
        if record_payload:
            latest.append(record_payload)
    headline = _safe_text(_get_nested(news, "latestHeadline", "headline"))
    if headline:
        latest.append({"kind": "news", "headline": headline})
    for record in _as_list(filing.get("records")):
        record_payload = _as_mapping(record)
        if record_payload:
            latest.append(record_payload)

    statuses = {str(block.get("status") or "").strip().lower() for block in (news, filing) if block}
    if latest:
        state = "available"
    elif not news and not filing:
        state = "not_integrated"
    elif statuses.intersection({"missing", "unavailable", "no_evidence", "insufficient", "unknown"}):
        state = "missing"
    else:
        state = "unknown"
    return {"state": state, "latest": latest}


def _peer_packet(structure: Mapping[str, Any] | None) -> dict[str, Any]:
    snapshot = _as_mapping(_get_nested(_as_mapping(structure), "peerCorrelationSnapshot", "peer_correlation_snapshot"))
    peer_group = _as_mapping(_get_nested(snapshot, "peerGroup", "peer_group"))
    peer_evidence = _as_list(_get_nested(snapshot, "peerEvidence", "peer_evidence"))
    correlation_state = str(_get_nested(snapshot, "correlationState", "correlation_state") or "").strip().lower()
    benchmark = _safe_text(peer_group.get("label"))

    if correlation_state in {"aligned", "diverging"} and peer_evidence:
        state = "available"
    elif peer_group.get("status") == "available":
        state = "insufficient"
    elif snapshot:
        state = "missing"
    else:
        state = "unknown"
    return {"state": state, "benchmark": benchmark if state == "available" else None}


def _missing_data_families(
    *,
    quote: Mapping[str, Any],
    history: Mapping[str, Any],
    structure: Mapping[str, Any],
    fundamentals: Mapping[str, Any],
    events: Mapping[str, Any],
    peer: Mapping[str, Any],
) -> list[str]:
    missing: list[str] = []
    if quote.get("state") != "available":
        missing.append("quote")
    if history.get("state") != "available":
        missing.append("price_history")
    if structure.get("state") != "available":
        missing.append("structure_analysis")
    if fundamentals.get("state") != "available":
        missing.append("fundamentals")
    if events.get("state") != "available":
        missing.append("filing_event_catalyst")
    if peer.get("state") != "available":
        missing.append("peer_benchmark")
    return missing


def _research_status(packet_parts: Mapping[str, Mapping[str, Any]]) -> str:
    critical_states = {
        str(packet_parts["quote"].get("state")),
        str(packet_parts["history"].get("state")),
        str(packet_parts["structure"].get("state")),
    }
    if critical_states.intersection({"missing", "unknown"}):
        return "blocked"
    if any(part.get("state") != "available" for part in packet_parts.values()):
        return "partial"
    return "ready"


def _next_data_action(missing_data: list[str], research_status: str) -> str:
    if research_status == "ready":
        return "Refresh the packet before reusing this research context."
    if "quote" in missing_data or "price_history" in missing_data:
        return "Add quote and daily price history evidence before marking the packet ready."
    if "structure_analysis" in missing_data:
        return "Add enough daily price history to build the structure observation."
    labels = {
        "fundamentals": "fundamentals",
        "filing_event_catalyst": "filing, event, or catalyst evidence",
        "peer_benchmark": "peer or benchmark evidence",
    }
    families = [labels[key] for key in missing_data if key in labels]
    if families:
        return f"Add {', '.join(families)} before marking the packet ready."
    return "Review missing data before interpreting this packet."


def _fail_closed_research_packet(precheck: ConsumerSymbolPrecheck) -> dict[str, Any]:
    normalized_symbol = precheck.normalized_symbol or precheck.raw_symbol
    missing_data = ["quote", "price_history", "structure_analysis", "fundamentals", "filing_event_catalyst", "peer_benchmark"]
    return {
        "symbol": normalized_symbol,
        "market": precheck.market or "unknown",
        "identity": {"name": None, "exchange": None, "sector": None, "industry": None},
        "quote": {"state": "unknown", "price": None, "changePercent": None, "asOf": None},
        "history": {"state": "unknown", "bars": 0, "period": "daily", "asOf": None},
        "structure": {"state": "unknown", "label": None, "confidence": None, "asOf": None},
        "fundamentals": {"state": "unknown", "fieldsAvailable": []},
        "events": {"state": "unknown", "latest": []},
        "peer": {"state": "unknown", "benchmark": None},
        "missingData": missing_data,
        "researchStatus": "blocked",
        "nextDataAction": "Verify symbol format and market before requesting research data.",
        "observationOnly": True,
        "decisionGrade": False,
        "noAdviceDisclosure": _RESEARCH_PACKET_NO_ADVICE_DISCLOSURE,
    }


def _build_symbol_research_packet(stock_code: str, *, market: Optional[str] = None) -> dict[str, Any]:
    precheck = validate_consumer_symbol_precheck(stock_code, market=market)
    if not precheck.can_lookup:
        return _fail_closed_research_packet(precheck)

    symbol = precheck.normalized_symbol
    stock_service = StockService()

    try:
        quote_payload = stock_service.get_realtime_quote(symbol)
    except Exception:
        logger.warning("Symbol research packet quote lookup failed for %s", symbol, exc_info=True)
        quote_payload = None

    try:
        history_payload = stock_service.get_history_data(
            stock_code=symbol,
            period="daily",
            days=_RESEARCH_PACKET_HISTORY_DAYS,
        )
    except Exception:
        logger.warning("Symbol research packet history lookup failed for %s", symbol, exc_info=True)
        history_payload = {}

    try:
        structure_payload = StockStructureDecisionService().get_structure_decision(symbol)
    except Exception:
        logger.warning("Symbol research packet structure lookup failed for %s", symbol, exc_info=True)
        structure_payload = {}

    try:
        evidence_service = StockEvidenceService()
        if hasattr(evidence_service, "quote_adapter") and hasattr(evidence_service.quote_adapter, "fetcher_manager"):
            evidence_service.quote_adapter.fetcher_manager = _ReadOnlyEvidenceFetcherManager()
        if hasattr(evidence_service, "fetcher_manager"):
            evidence_service.fetcher_manager = _ReadOnlyEvidenceFetcherManager()
        evidence_payload = evidence_service.get_stock_evidence([symbol])
    except Exception:
        logger.warning("Symbol research packet evidence lookup failed for %s", symbol, exc_info=True)
        evidence_payload = {}

    quote = _quote_packet(_as_mapping(quote_payload))
    history = _history_packet(_as_mapping(history_payload))
    structure = _structure_packet(_as_mapping(structure_payload))
    evidence_item = _first_evidence_item(_as_mapping(evidence_payload), symbol)
    fundamentals = _fundamentals_packet(evidence_item)
    events = _events_packet(evidence_item)
    peer = _peer_packet(_as_mapping(structure_payload))
    missing_data = _missing_data_families(
        quote=quote,
        history=history,
        structure=structure,
        fundamentals=fundamentals,
        events=events,
        peer=peer,
    )
    packet_parts = {
        "quote": quote,
        "history": history,
        "structure": structure,
        "fundamentals": fundamentals,
        "events": events,
        "peer": peer,
    }
    research_status = _research_status(packet_parts)
    name = _consumer_safe_stock_name(
        _get_nested(_as_mapping(quote_payload), "stock_name", "stockName")
        or _get_nested(_as_mapping(history_payload), "stock_name", "stockName"),
        symbol,
    )

    return {
        "symbol": symbol,
        "market": precheck.market or "unknown",
        "identity": {"name": name, "exchange": None, "sector": None, "industry": None},
        "quote": quote,
        "history": history,
        "structure": structure,
        "fundamentals": fundamentals,
        "events": events,
        "peer": peer,
        "missingData": missing_data,
        "researchStatus": research_status,
        "nextDataAction": _next_data_action(missing_data, research_status),
        "observationOnly": True,
        "decisionGrade": False,
        "noAdviceDisclosure": _RESEARCH_PACKET_NO_ADVICE_DISCLOSURE,
    }


@router.post(
    "/extract-from-image",
    response_model=ExtractFromImageResponse,
    responses={
        200: {"description": "提取的股票代码"},
        400: {"description": "图片无效", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="从图片提取股票代码",
    description="上传截图/图片，通过 Vision LLM 提取股票代码。支持 JPEG、PNG、WebP、GIF，最大 5MB。",
)
def extract_from_image(
    file: Optional[UploadFile] = File(None, description="图片文件（表单字段名 file）"),
    include_raw: bool = Query(False, description="是否在结果中包含原始 LLM 响应"),
) -> ExtractFromImageResponse:
    """
    从上传的图片中提取股票代码（使用 Vision LLM）。

    表单字段请使用 file 上传图片。优先级：Gemini / Anthropic / OpenAI（首个可用）。
    """
    if not file or not file.filename:
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_request", "message": "未提供文件，请使用表单字段 file 上传图片"},
        )

    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in ALLOWED_MIME:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "unsupported_type",
                "message": f"不支持的类型: {content_type}。允许: {ALLOWED_MIME_STR}",
            },
        )

    try:
        # 先读取限定大小，再检查是否还有剩余（语义清晰：超出则拒绝）
        data = file.file.read(MAX_SIZE_BYTES)
        if file.file.read(1):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "file_too_large",
                    "message": f"图片超过 {MAX_SIZE_BYTES // (1024 * 1024)}MB 限制",
                },
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"读取上传文件失败: {e}")
        raise HTTPException(
            status_code=400,
            detail={"error": "read_failed", "message": "读取上传文件失败"},
        )

    try:
        items, raw_text = extract_stock_codes_from_image(data, content_type)
        extract_items = [
            ExtractItem(code=code, name=name, confidence=conf) for code, name, conf in items
        ]
        codes = [i.code for i in extract_items]
        return ExtractFromImageResponse(
            codes=codes,
            items=extract_items,
            raw_text=raw_text if include_raw else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": "extract_failed", "message": str(e)})
    except Exception as e:
        logger.error(f"图片提取失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": "图片提取失败"},
        )


@router.post(
    "/parse-import",
    response_model=ExtractFromImageResponse,
    responses={
        200: {"description": "解析结果"},
        400: {"description": "未提供数据或解析失败", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="解析 CSV/Excel/剪贴板",
    description="上传 CSV/Excel 文件或粘贴文本，自动解析股票代码。文件上限 2MB，文本上限 100KB。",
)
async def parse_import(request: Request) -> ExtractFromImageResponse:
    """
    解析 CSV/Excel 文件或剪贴板文本。

    - multipart/form-data + file: 上传文件
    - application/json + {"text": "..."}: 粘贴文本
    - 优先使用 file，若同时提供则忽略 text
    """
    content_type = (request.headers.get("content-type") or "").lower()

    if "application/json" in content_type:
        try:
            body = await request.json()
        except Exception as e:
            logger.warning("[parse_import] JSON parse failed: %s", e)
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_json", "message": f"JSON 解析失败: {e}"},
            )
        text = body.get("text") if isinstance(body, dict) else None
        if not text or not isinstance(text, str):
            raise HTTPException(
                status_code=400,
                detail={"error": "bad_request", "message": "未提供 text，请使用 {\"text\": \"...\"}"},
            )
        try:
            items = parse_import_from_text(text)
        except ValueError as e:
            text_bytes = len(text.encode("utf-8"))
            logger.warning(
                "[parse_import] parse_import_from_text failed: text_bytes=%d, error=%s",
                text_bytes,
                e,
            )
            raise HTTPException(status_code=400, detail={"error": "parse_failed", "message": str(e)})
    elif "multipart" in content_type:
        form = await request.form()
        file = form.get("file")
        if not file or not hasattr(file, "read"):
            raise HTTPException(
                status_code=400,
                detail={"error": "bad_request", "message": "未提供文件，请使用表单字段 file"},
            )
        file_size = getattr(file, "size", None)
        if isinstance(file_size, int) and file_size > MAX_FILE_BYTES:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "file_too_large",
                    "message": f"文件超过 {MAX_FILE_BYTES // (1024 * 1024)}MB 限制",
                },
            )
        try:
            data = file.file.read(MAX_FILE_BYTES)
            if file.file.read(1):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "file_too_large",
                        "message": f"文件超过 {MAX_FILE_BYTES // (1024 * 1024)}MB 限制",
                    },
                )
        except HTTPException:
            raise
        except Exception as e:
            filename = getattr(file, "filename", None) or ""
            size = getattr(file, "size", None)
            logger.warning(
                "[parse_import] file read failed: filename=%r, size=%s, error=%s",
                filename,
                size,
                e,
            )
            raise HTTPException(
                status_code=400,
                detail={"error": "read_failed", "message": "读取文件失败"},
            )
        filename = getattr(file, "filename", None) or ""
        try:
            items = parse_import_from_bytes(data, filename=filename)
        except ValueError as e:
            ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            logger.warning(
                "[parse_import] parse_import_from_bytes failed: filename=%r, ext=%r, bytes=%d, error=%s",
                filename,
                ext,
                len(data),
                e,
            )
            raise HTTPException(status_code=400, detail={"error": "parse_failed", "message": str(e)})
    else:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "bad_request",
                "message": "请使用 multipart/form-data 上传文件，或 application/json 提交 {\"text\": \"...\"}",
            },
        )

    extract_items = [
        ExtractItem(code=code, name=name, confidence=conf)
        for code, name, conf in items
    ]
    codes = list(dict.fromkeys(i.code for i in extract_items if i.code))
    return ExtractFromImageResponse(codes=codes, items=extract_items, raw_text=None)


@router.get(
    "/{stock_code}/validate",
    response_model=StockValidationResponse,
    responses={
        200: {"description": "股票代码真实性校验结果"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="校验股票代码是否存在",
    description="在触发分析前校验股票代码是否能解析为真实标的",
)
def validate_stock_ticker(
    stock_code: str,
    market: Optional[str] = Query(None, description="可选市场约束：cn / hk / us"),
) -> StockValidationResponse:
    return _validate_stock_ticker(stock_code, market=market)


def _validate_stock_ticker(
    stock_code: str,
    market: Optional[str] = None,
) -> StockValidationResponse:
    precheck = validate_consumer_symbol_precheck(stock_code, market=market)
    if not precheck.can_lookup:
        return _stock_validation_response(precheck)

    try:
        service = StockService()
        result = service.validate_ticker_exists(precheck.normalized_symbol)
    except Exception:
        logger.warning("Stock symbol validation lookup unavailable for %s", precheck.normalized_symbol)
        return _stock_validation_response(
            precheck,
            status="unavailable",
            valid=False,
            exists=False,
            stock_name=None,
            message=_VALIDATION_UNAVAILABLE_MESSAGE,
        )

    if bool(result.get("exists")):
        return _stock_validation_response(
            precheck,
            status="valid",
            valid=True,
            exists=True,
            stock_name=result.get("stock_name"),
            message=_VALIDATION_VERIFIED_MESSAGE,
        )

    return _stock_validation_response(
        precheck,
        status="unknown",
        valid=False,
        exists=False,
        stock_name=None,
        message=_VALIDATION_UNKNOWN_MESSAGE,
    )


@router.get(
    "/{stock_code}/research-packet",
    response_model=SymbolResearchPacketResponse,
    response_model_exclude_none=False,
    responses={
        200: {"description": "单股票最小 research packet"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取单股票最小 research packet",
    description="返回 Stock Detail 和 Watchlist 可复用的最小研究数据覆盖状态；不构成交易建议。",
)
def get_symbol_research_packet(
    stock_code: str,
    market: Optional[str] = Query(None, description="可选市场约束：cn / hk / us"),
) -> SymbolResearchPacketResponse:
    try:
        payload = _build_symbol_research_packet(stock_code, market=market)
        return consumer_safe_json_response(
            SymbolResearchPacketResponse.model_validate(payload),
            surface="symbol-research-packet",
            exclude_none=False,
        )
    except Exception as e:
        logger.error("获取股票 research packet 失败: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": "获取股票 research packet 失败",
            },
        )


@router.post(
    "/structure-decisions/batch",
    response_model=StockStructureDecisionBatchResponse,
    response_model_exclude_none=True,
    responses={
        200: {"description": "批量股票结构判断"},
        422: {"description": "请求参数无效", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="批量获取股票结构判断",
    description="返回多个股票的观察型结构判断和批量比较摘要；不生成操作指令。",
)
def get_stock_structure_decisions_batch(
    request: StockStructureDecisionBatchRequest,
) -> StockStructureDecisionBatchResponse:
    try:
        payload = StockStructureDecisionService().get_structure_decisions_batch(
            request.stock_codes,
            benchmark=request.benchmark,
            max_items=request.max_items,
        )
        return consumer_safe_json_response(
            StockStructureDecisionBatchResponse.model_validate(payload),
            surface="stock-structure-decision-batch",
            exclude_none=True,
        )
    except Exception as e:
        logger.error("批量获取股票结构判断失败: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": "批量获取股票结构判断失败",
            },
        )


@router.get(
    "/{stock_code}/evidence",
    response_model=StockEvidenceResponse,
    response_model_exclude_none=True,
    responses={
        200: {"description": "单股票只读证据数据"},
        404: {"description": "股票不存在或代码无效", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取单股票只读证据",
    description="返回现有 StockEvidenceService 的单股票只读证据投影，并保留 stockEvidencePacket。",
)
def get_stock_evidence(stock_code: str) -> StockEvidenceResponse:
    try:
        service = StockEvidenceService()
        if hasattr(service, "quote_adapter") and hasattr(service.quote_adapter, "fetcher_manager"):
            service.quote_adapter.fetcher_manager = _ReadOnlyEvidenceFetcherManager()
        if hasattr(service, "fetcher_manager"):
            service.fetcher_manager = _ReadOnlyEvidenceFetcherManager()
        payload = service.get_stock_evidence([stock_code])

        items = payload.get("items")
        if not isinstance(items, list) or not items:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "not_found",
                    "message": f"未找到股票 {stock_code} 的证据数据",
                },
            )

        return consumer_safe_json_response(
            StockEvidenceResponse.model_validate(payload),
            surface="stock-evidence",
            exclude_none=True,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取股票证据失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"获取股票证据失败: {str(e)}",
            },
        )


@router.get(
    "/{stock_code}/structure-decision",
    response_model=StockStructureDecisionResponse,
    response_model_exclude_none=True,
    responses={
        200: {"description": "单股票结构判断"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取股票结构判断",
    description="返回 Stock Structure Decision Engine 的观察型结构判断；不构成交易建议。",
)
def get_stock_structure_decision(
    stock_code: str,
    context_source: Optional[str] = Query(None, alias="contextSource", description="可选来源上下文：researchRadar / watchlist / portfolio"),
    context_section: Optional[str] = Query(None, alias="contextSection", description="可选来源区段"),
    context_reason: Optional[str] = Query(None, alias="contextReason", description="可选来源原因提示"),
) -> StockStructureDecisionResponse:
    try:
        payload = StockStructureDecisionService().get_structure_decision(
            stock_code,
            context_source=context_source,
            context_section=context_section,
            context_reason=context_reason,
        )
        return consumer_safe_json_response(
            StockStructureDecisionResponse.model_validate(payload),
            surface="stock-structure-decision",
            exclude_none=True,
        )
    except Exception as e:
        logger.error("获取股票结构判断失败: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": "获取股票结构判断失败",
            },
        )


@router.get(
    "/{stock_code}/quote",
    response_model=StockQuote,
    responses={
        200: {"description": "行情数据"},
        404: {"description": "股票不存在", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取股票实时行情",
    description="获取指定股票的最新行情数据"
)
def get_stock_quote(stock_code: str) -> StockQuote:
    """
    获取股票实时行情
    
    获取指定股票的最新行情数据
    
    Args:
        stock_code: 股票代码（如 600519、00700、AAPL）
        
    Returns:
        StockQuote: 实时行情数据
        
    Raises:
        HTTPException: 404 - 股票不存在
    """
    try:
        service = StockService()
        
        # 使用 def 而非 async def，FastAPI 自动在线程池中执行
        result = service.get_realtime_quote(stock_code)
        
        if result is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "not_found",
                    "message": f"未找到股票 {stock_code} 的行情数据"
                }
            )
        
        return StockQuote(
            stock_code=result.get("stock_code", stock_code),
            stock_name=result.get("stock_name"),
            current_price=result.get("current_price", 0.0),
            change=result.get("change"),
            change_percent=result.get("change_percent"),
            open=result.get("open"),
            high=result.get("high"),
            low=result.get("low"),
            prev_close=result.get("prev_close"),
            volume=result.get("volume"),
            amount=result.get("amount"),
            update_time=result.get("update_time"),
            source=result.get("source"),
            source_type=result.get("sourceType") or result.get("source_type"),
            market_timestamp=result.get("marketTimestamp") or result.get("market_timestamp"),
            observed_at=result.get("observedAt") or result.get("observed_at"),
            freshness=result.get("freshness"),
            is_fallback=result.get("isFallback") if "isFallback" in result else result.get("is_fallback"),
            is_stale=result.get("isStale") if "isStale" in result else result.get("is_stale"),
            is_partial=result.get("isPartial") if "isPartial" in result else result.get("is_partial"),
            is_synthetic=result.get("isSynthetic") if "isSynthetic" in result else result.get("is_synthetic"),
            source_confidence=result.get("sourceConfidence") or result.get("source_confidence"),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取实时行情失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"获取实时行情失败: {str(e)}"
            }
        )


@router.get(
    "/{stock_code}/intraday",
    response_model=StockIntradayResponse,
    responses={
        200: {"description": "日内行情数据"},
        422: {"description": "不支持的参数", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取股票日内行情",
    description="获取指定股票的分钟级 / 日内行情，供图表与快照分析使用",
)
def get_stock_intraday(
    stock_code: str,
    interval: str = Query("5m", description="分钟间隔", pattern="^(1m|2m|5m|15m|30m|60m|90m)$"),
    range_period: str = Query("1d", alias="range", description="时间范围", pattern="^(1d|5d|1mo)$"),
) -> StockIntradayResponse:
    try:
        service = StockService()
        result = service.get_intraday_data(
            stock_code=stock_code,
            interval=interval,
            range_period=range_period,
        )
        data = [
            IntradayBar(
                time=item.get("time"),
                open=item.get("open"),
                high=item.get("high"),
                low=item.get("low"),
                close=item.get("close"),
                volume=item.get("volume"),
            )
            for item in result.get("data", [])
        ]
        return StockIntradayResponse(
            stock_code=stock_code,
            stock_name=result.get("stock_name"),
            interval=interval,
            range=range_period,
            source=result.get("source"),
            source_type=result.get("sourceType") or result.get("source_type"),
            freshness=result.get("freshness"),
            is_fallback=result.get("isFallback") if "isFallback" in result else result.get("is_fallback"),
            is_stale=result.get("isStale") if "isStale" in result else result.get("is_stale"),
            is_partial=result.get("isPartial") if "isPartial" in result else result.get("is_partial"),
            is_synthetic=result.get("isSynthetic") if "isSynthetic" in result else result.get("is_synthetic"),
            is_unavailable=result.get("isUnavailable") if "isUnavailable" in result else result.get("is_unavailable"),
            source_confidence=result.get("sourceConfidence") or result.get("source_confidence"),
            data=data,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "unsupported_intraday_param",
                "message": str(e),
            },
        )
    except Exception as e:
        logger.error(f"获取日内行情失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"获取日内行情失败: {str(e)}",
            },
        )


@router.get(
    "/{stock_code}/history",
    response_model=StockHistoryResponse,
    responses={
        200: {"description": "历史行情数据"},
        422: {"description": "不支持的周期参数", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取股票历史行情",
    description="获取指定股票的历史 K 线数据"
)
def get_stock_history(
    stock_code: str,
    period: str = Query("daily", description="K 线周期", pattern="^(daily|weekly|monthly|yearly)$"),
    days: int = Query(30, ge=1, le=3650, description="获取天数")
) -> StockHistoryResponse:
    """
    获取股票历史行情
    
    获取指定股票的历史 K 线数据
    
    Args:
        stock_code: 股票代码
        period: K 线周期 (daily/weekly/monthly/yearly)
        days: 获取天数
        
    Returns:
        StockHistoryResponse: 历史行情数据
    """
    try:
        service = StockService()
        
        # 使用 def 而非 async def，FastAPI 自动在线程池中执行
        result = service.get_history_data(
            stock_code=stock_code,
            period=period,
            days=days
        )
        
        # 转换为响应模型
        data = [
            KLineData(
                date=item.get("date"),
                open=item.get("open"),
                high=item.get("high"),
                low=item.get("low"),
                close=item.get("close"),
                volume=item.get("volume"),
                amount=item.get("amount"),
                change_percent=item.get("change_percent")
            )
            for item in result.get("data", [])
        ]
        
        return StockHistoryResponse(
            stock_code=stock_code,
            stock_name=result.get("stock_name"),
            period=period,
            data=data,
            source=result.get("source"),
            diagnostics=result.get("diagnostics"),
            source_confidence=result.get("sourceConfidence") or result.get("source_confidence"),
        )
    
    except ValueError as e:
        # period 参数不支持的错误（如 weekly/monthly）
        raise HTTPException(
            status_code=422,
            detail={
                "error": "unsupported_period",
                "message": str(e)
            }
        )
    except Exception as e:
        logger.error(f"获取历史行情失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"获取历史行情失败: {str(e)}"
            }
        )
