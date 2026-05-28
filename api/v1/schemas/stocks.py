# -*- coding: utf-8 -*-
"""
===================================
股票数据相关模型
===================================

职责：
1. 定义股票实时行情模型
2. 定义历史 K 线数据模型
"""

from typing import Any, Dict, Optional, List

from pydantic import BaseModel, ConfigDict, Field


class StockQuote(BaseModel):
    """股票实时行情"""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "stock_code": "600519",
                "stock_name": "贵州茅台",
                "current_price": 1800.00,
                "change": 15.00,
                "change_percent": 0.84,
                "open": 1785.00,
                "high": 1810.00,
                "low": 1780.00,
                "prev_close": 1785.00,
                "volume": 10000000,
                "amount": 18000000000,
                "update_time": "2024-01-01T15:00:00",
                "source": "efinance",
                "sourceType": "provider_runtime",
                "marketTimestamp": "2024-01-01T14:59:57+08:00",
                "observedAt": "2024-01-01T15:00:00+08:00",
                "freshness": "live",
                "isFallback": False,
                "isStale": False,
                "isPartial": False,
                "isSynthetic": False,
            }
        }
    )

    stock_code: str = Field(..., description="股票代码")
    stock_name: Optional[str] = Field(None, description="股票名称")
    current_price: float = Field(..., description="当前价格")
    change: Optional[float] = Field(None, description="涨跌额")
    change_percent: Optional[float] = Field(None, description="涨跌幅 (%)")
    open: Optional[float] = Field(None, description="开盘价")
    high: Optional[float] = Field(None, description="最高价")
    low: Optional[float] = Field(None, description="最低价")
    prev_close: Optional[float] = Field(None, description="昨收价")
    volume: Optional[float] = Field(None, description="成交量（股）")
    amount: Optional[float] = Field(None, description="成交额（元）")
    update_time: Optional[str] = Field(None, description="服务端观察/封装该行情的时间（兼容旧字段）")
    source: Optional[str] = Field(None, description="上游 provider 报告的行情来源")
    source_type: Optional[str] = Field(None, alias="sourceType", description="行情来源类型")
    market_timestamp: Optional[str] = Field(None, alias="marketTimestamp", description="上游 provider 报告的市场时间")
    observed_at: Optional[str] = Field(None, alias="observedAt", description="服务端观察到该行情的时间")
    freshness: Optional[str] = Field(None, description="行情新鲜度标签")
    is_fallback: Optional[bool] = Field(None, alias="isFallback", description="是否为 fallback 行情")
    is_stale: Optional[bool] = Field(None, alias="isStale", description="是否已标记为 stale")
    is_partial: Optional[bool] = Field(None, alias="isPartial", description="是否缺少部分 freshness/provenance 信息")
    is_synthetic: Optional[bool] = Field(None, alias="isSynthetic", description="是否为本地合成/占位行情")
    source_confidence: Optional[Dict[str, Any]] = Field(None, alias="sourceConfidence", description="行情来源可信度元信息")


class KLineData(BaseModel):
    """K 线数据点"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "date": "2024-01-01",
                "open": 1785.00,
                "high": 1810.00,
                "low": 1780.00,
                "close": 1800.00,
                "volume": 10000000,
                "amount": 18000000000,
                "change_percent": 0.84,
            }
        }
    )

    date: str = Field(..., description="日期")
    open: float = Field(..., description="开盘价")
    high: float = Field(..., description="最高价")
    low: float = Field(..., description="最低价")
    close: float = Field(..., description="收盘价")
    volume: Optional[float] = Field(None, description="成交量")
    amount: Optional[float] = Field(None, description="成交额")
    change_percent: Optional[float] = Field(None, description="涨跌幅 (%)")


class ExtractItem(BaseModel):
    """单条提取结果（代码、名称、置信度）"""

    code: Optional[str] = Field(None, description="股票代码，None 表示解析失败")
    name: Optional[str] = Field(None, description="股票名称（如有）")
    confidence: str = Field("medium", description="置信度：high/medium/low")


class ExtractFromImageResponse(BaseModel):
    """图片股票代码提取响应"""

    codes: List[str] = Field(..., description="提取的股票代码（已去重，向后兼容）")
    items: List[ExtractItem] = Field(default_factory=list, description="提取结果明细（代码+名称+置信度）")
    raw_text: Optional[str] = Field(None, description="原始 LLM 响应（调试用）")


class StockHistoryResponse(BaseModel):
    """股票历史行情响应"""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "stock_code": "600519",
                "stock_name": "贵州茅台",
                "period": "daily",
                "data": [],
                "source": "unavailable",
                "diagnostics": {
                    "status": "unavailable",
                    "reason": "history_unavailable",
                    "message": "No real OHLC daily history is currently available.",
                },
            }
        }
    )

    stock_code: str = Field(..., description="股票代码")
    stock_name: Optional[str] = Field(None, description="股票名称")
    period: str = Field(..., description="K 线周期")
    data: List[KLineData] = Field(default_factory=list, description="K 线数据列表")
    source: Optional[str] = Field(None, description="历史行情数据来源")
    diagnostics: Optional[Dict[str, Any]] = Field(None, description="历史行情数据可用性诊断")
    source_confidence: Optional[Dict[str, Any]] = Field(None, alias="sourceConfidence", description="数据来源可信度元信息")


class IntradayBar(BaseModel):
    """分钟 / 日内行情数据点"""

    time: str = Field(..., description="时间戳")
    open: float = Field(..., description="开盘价")
    high: float = Field(..., description="最高价")
    low: float = Field(..., description="最低价")
    close: float = Field(..., description="收盘价")
    volume: Optional[float] = Field(None, description="成交量")


class StockIntradayResponse(BaseModel):
    """股票日内行情响应"""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "stock_code": "AAPL",
                "stock_name": "Apple",
                "interval": "5m",
                "range": "1d",
                "source": "yfinance",
                "sourceType": "unofficial_proxy",
                "freshness": "delayed",
                "isFallback": False,
                "isStale": False,
                "isPartial": False,
                "isSynthetic": False,
                "isUnavailable": False,
                "sourceConfidence": {
                    "source": "yfinance",
                    "sourceLabel": "Yahoo Finance intraday proxy",
                    "asOf": "2026-05-28T09:35:00+00:00",
                    "freshness": "delayed",
                    "isFallback": False,
                    "isStale": False,
                    "isPartial": False,
                    "isSynthetic": False,
                    "isUnavailable": False,
                    "confidenceWeight": 0.7,
                    "coverage": 1.0,
                    "degradationReason": "delayed_source",
                    "capReason": None,
                },
                "data": [],
            }
        },
    )

    stock_code: str = Field(..., description="股票代码")
    stock_name: Optional[str] = Field(None, description="股票名称")
    interval: str = Field(..., description="分钟间隔")
    range: str = Field(..., description="时间范围")
    source: Optional[str] = Field(None, description="数据源")
    source_type: Optional[str] = Field(None, alias="sourceType", description="数据源类型")
    freshness: Optional[str] = Field(None, description="日内行情新鲜度标签")
    is_fallback: Optional[bool] = Field(None, alias="isFallback", description="是否为 fallback 日内行情")
    is_stale: Optional[bool] = Field(None, alias="isStale", description="是否已标记为 stale")
    is_partial: Optional[bool] = Field(None, alias="isPartial", description="是否缺少部分 provenance 信息")
    is_synthetic: Optional[bool] = Field(None, alias="isSynthetic", description="是否为合成/占位日内行情")
    is_unavailable: Optional[bool] = Field(None, alias="isUnavailable", description="是否明确不可用")
    source_confidence: Optional[Dict[str, Any]] = Field(None, alias="sourceConfidence", description="日内行情来源可信度元信息")
    data: List[IntradayBar] = Field(default_factory=list, description="分钟行情列表")


class StockValidationResponse(BaseModel):
    """股票代码真实性校验响应"""

    stock_code: str = Field(..., description="股票代码")
    exists: bool = Field(..., description="股票代码是否存在")
    stock_name: Optional[str] = Field(None, description="解析出的股票名称")
