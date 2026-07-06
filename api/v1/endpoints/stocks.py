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
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile

from api.deps import CurrentUser, get_current_user
from api.v1.consumer_safe_response import consumer_safe_json_response
from api.v1.errors import safe_api_error
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
from src.services.product_read_model import build_stock_evidence_product_read_model
from src.services.stock_service import StockService
from src.services.stock_structure_decision_service import StockStructureDecisionService
from src.services.symbol_research_packet_service import (
    _ReadOnlyEvidenceFetcherManager,
    build_symbol_research_packet,
    consumer_safe_stock_name,
)
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
_STOCK_EVIDENCE_INTERNAL_ERROR_MESSAGE = "Stock evidence is temporarily unavailable. Please retry later."
_STOCK_QUOTE_INTERNAL_ERROR_MESSAGE = "实时行情暂时不可用，请稍后重试。"


def _consumer_safe_quote_source(result: dict) -> str | None:
    source_confidence = result.get("sourceConfidence") or result.get("source_confidence")
    if isinstance(source_confidence, dict):
        label = str(source_confidence.get("sourceLabel") or "").strip()
        if label:
            return label
    label = str(result.get("sourceLabel") or result.get("source_label") or "").strip()
    if label:
        return label
    source = str(result.get("source") or "").strip()
    if not source:
        return None
    return source.replace("_", " ").title()


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
        stock_name=consumer_safe_stock_name(stock_name, normalized_symbol),
        message=message or precheck.message,
    )


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
        payload = build_symbol_research_packet(stock_code, market=market)
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
    current_user: CurrentUser = Depends(get_current_user),
) -> StockStructureDecisionBatchResponse:
    _ = current_user
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

        for item in items:
            if isinstance(item, dict) and not isinstance(item.get("productReadModel"), dict):
                item["productReadModel"] = build_stock_evidence_product_read_model(item)

        return consumer_safe_json_response(
            StockEvidenceResponse.model_validate(payload),
            surface="stock-evidence",
            exclude_none=True,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取股票证据失败: %s", e, exc_info=True)
        raise safe_api_error(
            status_code=500,
            error="internal_error",
            message=_STOCK_EVIDENCE_INTERNAL_ERROR_MESSAGE,
            retryable=True,
        ) from e


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
    current_user: CurrentUser = Depends(get_current_user),
) -> StockStructureDecisionResponse:
    _ = current_user
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
    response_model_exclude_none=True,
    responses={
        200: {"description": "行情数据"},
        404: {"description": "股票不存在", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取股票实时行情",
    description="获取指定股票的最新行情数据"
)
def get_stock_quote(
    stock_code: str,
) -> StockQuote:
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
            source=_consumer_safe_quote_source(result),
            source_type=result.get("sourceType") or result.get("source_type"),
            market_timestamp=result.get("marketTimestamp") or result.get("market_timestamp"),
            observed_at=result.get("observedAt") or result.get("observed_at"),
            freshness=result.get("freshness"),
            is_fallback=result.get("isFallback") if "isFallback" in result else result.get("is_fallback"),
            is_stale=result.get("isStale") if "isStale" in result else result.get("is_stale"),
            is_partial=result.get("isPartial") if "isPartial" in result else result.get("is_partial"),
            is_synthetic=result.get("isSynthetic") if "isSynthetic" in result else result.get("is_synthetic"),
            is_unavailable=result.get("isUnavailable") if "isUnavailable" in result else result.get("is_unavailable"),
            availability_state=result.get("availabilityState") or result.get("availability_state"),
            provider_state=result.get("providerState") or result.get("provider_state"),
            missing_requirements=result.get("missingRequirements") or result.get("missing_requirements") or [],
            unavailable_reason=result.get("unavailableReason") or result.get("unavailable_reason"),
            quote_readiness=result.get("quoteReadiness") or result.get("quote_readiness"),
            source_confidence=result.get("sourceConfidence") or result.get("source_confidence"),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取实时行情失败: {e}", exc_info=True)
        raise safe_api_error(
            status_code=500,
            error="internal_error",
            message=_STOCK_QUOTE_INTERNAL_ERROR_MESSAGE,
            retryable=True,
            fallback_message=_STOCK_QUOTE_INTERNAL_ERROR_MESSAGE,
        ) from e


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
    days: int = Query(90, ge=1, le=3650, description="获取天数")
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
            historical_ohlcv_readiness=result.get("historicalOhlcvReadiness") or result.get("historical_ohlcv_readiness"),
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
