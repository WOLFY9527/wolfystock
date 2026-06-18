# -*- coding: utf-8 -*-
"""
===================================
股票数据相关模型
===================================

职责：
1. 定义股票实时行情模型
2. 定义历史 K 线数据模型
"""

from typing import Annotated, Any, Dict, Optional, List, Literal

from pydantic import BaseModel, ConfigDict, Field, WithJsonSchema


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
    normalized_symbol: Optional[str] = Field(None, description="归一化后的股票代码")
    market: Optional[str] = Field(None, description="归属市场：cn/hk/us，无法判断时为空")
    status: Literal[
        "valid",
        "invalid_format",
        "unsupported_market",
        "ambiguous",
        "not_found",
        "unavailable",
        "unknown",
    ] = Field("unknown", description="消费端安全的符号校验状态")
    valid: bool = Field(False, description="是否已确认可安全用于下游研究")
    exists: bool = Field(..., description="股票代码是否存在")
    stock_name: Optional[str] = Field(None, description="解析出的股票名称")
    message: str = Field(
        "Symbol format is supported, but verification is not confirmed yet.",
        description="消费端安全提示文案",
    )


class StockEvidenceFundamentalsSummary(BaseModel):
    """单股票证据包中的 fundamentalsSummary 白名单投影。"""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    status: Optional[str] = Field(None, description="基本面摘要状态")
    market_cap: Optional[float] = Field(None, alias="marketCap", description="市值")
    pe_ttm: Optional[float] = Field(None, alias="peTtm", description="滚动市盈率")
    pb: Optional[float] = Field(None, description="市净率")
    beta: Optional[float] = Field(None, description="Beta")
    revenue_ttm: Optional[float] = Field(None, alias="revenueTtm", description="滚动营收")
    net_income_ttm: Optional[float] = Field(None, alias="netIncomeTtm", description="滚动净利润")
    fcf_ttm: Optional[float] = Field(None, alias="fcfTtm", description="滚动自由现金流")
    gross_margin: Optional[float] = Field(None, alias="grossMargin", description="毛利率")
    operating_margin: Optional[float] = Field(None, alias="operatingMargin", description="营业利润率")
    roe: Optional[float] = Field(None, description="净资产收益率")
    roa: Optional[float] = Field(None, description="总资产收益率")
    period: Optional[str] = Field(None, description="字段周期标签")
    source: Optional[str] = Field(None, description="来源标签")
    freshness: Optional[str] = Field(None, description="新鲜度标签")
    missing_fields: List[str] = Field(default_factory=list, alias="missingFields", description="缺失字段列表")
    not_investment_advice: Optional[bool] = Field(None, alias="notInvestmentAdvice", description="非投资建议")
    observation_only: Optional[bool] = Field(None, alias="observationOnly", description="仅观察")
    score_contribution_allowed: Optional[bool] = Field(None, alias="scoreContributionAllowed", description="是否允许参与打分")
    source_authority_allowed: Optional[bool] = Field(None, alias="sourceAuthorityAllowed", description="是否允许作为权威来源")


class StockEvidencePacketResponse(BaseModel):
    """单股票证据包响应。除 fundamentalsSummary 外保持兼容透传。"""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    fundamentals_summary: Optional[StockEvidenceFundamentalsSummary] = Field(
        None,
        alias="fundamentalsSummary",
        description="白名单过滤后的基本面摘要",
    )


class SymbolEvidenceReadinessResponse(BaseModel):
    """单股票证据就绪度包。"""

    model_config = ConfigDict(populate_by_name=True)

    symbol_evidence_readiness: Literal[True] = Field(
        ...,
        alias="symbolEvidenceReadiness",
        description="标识该对象为单股票证据就绪度包",
    )
    symbol: str = Field(..., description="归一化股票代码")
    readiness_tier: Literal["sufficient", "partial", "insufficient"] = Field(
        ...,
        alias="readinessTier",
        description="证据是否足够继续研究",
    )
    evidence_used: List[str] = Field(default_factory=list, alias="evidenceUsed", description="已使用的证据族")
    evidence_missing: List[str] = Field(default_factory=list, alias="evidenceMissing", description="缺失或不完整的证据族")
    stale_inputs: List[str] = Field(default_factory=list, alias="staleInputs", description="带有过期/延迟标记的输入")
    conflicting_evidence: List[str] = Field(default_factory=list, alias="conflictingEvidence", description="显式冲突证据族")
    data_quality_notes: List[str] = Field(default_factory=list, alias="dataQualityNotes", description="证据质量说明")
    suggested_research_path: List[str] = Field(default_factory=list, alias="suggestedResearchPath", description="下一步研究路径")
    observation_only: Literal[True] = Field(..., alias="observationOnly", description="仅观察，不输出交易动作")
    no_advice_disclosure: str = Field(..., alias="noAdviceDisclosure", description="非个性化建议披露")


_STOCK_EVIDENCE_ITEM_METADATA_SCHEMA = {
    "type": "object",
    "additionalProperties": True,
    "properties": {
        "status": {"type": "string"},
        "provider": {"type": "string"},
        "providerId": {"type": "string"},
        "providerName": {"type": "string"},
        "source": {"type": "string"},
        "sourceType": {"type": "string"},
        "sourceTier": {"type": "string"},
        "trustLevel": {"type": "string"},
        "freshness": {"type": "string"},
        "updatedAt": {"type": "string"},
        "asOf": {"type": "string"},
        "degradationReason": {"type": "string"},
        "isFallback": {"type": "boolean"},
        "isStale": {"type": "boolean"},
        "isPartial": {"type": "boolean"},
        "isSynthetic": {"type": "boolean"},
        "isUnavailable": {"type": "boolean"},
        "sourceConfidence": {"type": "object", "additionalProperties": True},
        "observationOnly": {"type": "boolean"},
        "scoreContributionAllowed": {"type": "boolean"},
        "sourceAuthorityAllowed": {"type": "boolean"},
        "rawPayloadStored": {"type": "boolean"},
        "missingFields": {"type": "array", "items": {"type": "string"}},
        "freshnessExpectation": {"type": "string"},
        "records": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
    },
}

StockEvidenceItemMetadataDict = Annotated[
    Dict[str, Any],
    WithJsonSchema(_STOCK_EVIDENCE_ITEM_METADATA_SCHEMA),
]


class StockEvidenceItemResponse(BaseModel):
    """单股票证据响应项。"""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    symbol: str = Field(..., description="股票代码")
    market: Optional[str] = Field(None, description="市场代码")
    quote: Optional[StockEvidenceItemMetadataDict] = Field(None, description="行情侧证据")
    technical: Optional[StockEvidenceItemMetadataDict] = Field(None, description="技术面证据")
    fundamental: Optional[StockEvidenceItemMetadataDict] = Field(None, description="基本面证据")
    news: Optional[StockEvidenceItemMetadataDict] = Field(None, description="新闻证据")
    sec_filing_evidence: Optional[StockEvidenceItemMetadataDict] = Field(
        None,
        alias="secFilingEvidence",
        description="SEC filing 侧证据",
    )
    stock_evidence_packet: Optional[StockEvidencePacketResponse] = Field(
        None,
        alias="stockEvidencePacket",
        description="现有 stock evidence packet 投影",
    )
    symbol_evidence_readiness: Optional[SymbolEvidenceReadinessResponse] = Field(
        None,
        alias="symbolEvidenceReadiness",
        description="单股票证据就绪度包",
    )


class StockEvidenceMetaResponse(BaseModel):
    """单股票证据响应元信息。"""

    model_config = ConfigDict(populate_by_name=True)

    generated_at: Optional[str] = Field(None, alias="generatedAt", description="生成时间")
    source: Optional[str] = Field(None, description="来源标签")


class StockEvidenceResponse(BaseModel):
    """单股票证据接口响应。"""

    model_config = ConfigDict(populate_by_name=True)

    symbols: List[str] = Field(default_factory=list, description="归一化后的股票代码列表")
    items: List[StockEvidenceItemResponse] = Field(default_factory=list, description="单股票证据项列表")
    meta: Optional[StockEvidenceMetaResponse] = Field(None, description="响应元信息")


class StockStructureDecisionDataQuality(BaseModel):
    """结构判断输入数据质量。"""

    status: Literal["available", "partial", "insufficient", "unavailable"] = Field(
        ...,
        description="OHLCV 证据可用性状态",
    )
    source: str = Field(..., description="历史行情来源标签")
    period: str = Field(..., description="使用的 K 线周期")
    requested_days: int = Field(..., alias="requestedDays", description="请求的历史天数")
    observed_bars: int = Field(..., alias="observedBars", description="观察到的日线数量")
    usable_bars: int = Field(..., alias="usableBars", description="可用于结构判断的日线数量")
    reason: str = Field(..., description="数据质量原因码")


class StockStructureDecisionMissingEvidence(BaseModel):
    """结构判断缺失证据项。"""

    kind: str = Field(..., description="缺失证据类型")
    message: str = Field(..., description="面向研究使用的缺失证据说明")


class StockStructureDecisionComparativeContext(BaseModel):
    """单股票结构判断中的比较上下文。"""

    model_config = ConfigDict(populate_by_name=True)

    status: Literal["available", "unavailable"] = Field(..., description="比较上下文状态")
    benchmark: Optional[str] = Field(None, description="用于比较的基准代码")
    relative_strength_score: Optional[int] = Field(None, alias="relativeStrengthScore", description="相对强度分数")
    rank: Optional[int] = Field(None, description="相对强度排序")
    reason: Optional[str] = Field(None, description="不可用原因码")


class StockSymbolCompareConfidenceCap(BaseModel):
    """多股票比较证据包的置信上限。"""

    model_config = ConfigDict(populate_by_name=True)

    value: int = Field(..., ge=0, le=100, description="比较观察置信上限")
    reason_codes: List[str] = Field(default_factory=list, alias="reasonCodes", description="置信上限原因码")
    policy_version: str = Field(..., alias="policyVersion", description="置信上限策略版本")


class StockSymbolCompareObservationBoundary(BaseModel):
    """多股票比较证据包的观察边界。"""

    model_config = ConfigDict(populate_by_name=True)

    observation_only: Literal[True] = Field(..., alias="observationOnly", description="仅观察")
    decision_grade: Literal[False] = Field(..., alias="decisionGrade", description="不输出决策等级")
    ranking_allowed: Literal[False] = Field(..., alias="rankingAllowed", description="不输出排名")
    advice_allowed: Literal[False] = Field(..., alias="adviceAllowed", description="不输出建议")


class StockSymbolCompareEvidencePacket(BaseModel):
    """多股票比较证据包，仅描述覆盖、分歧、缺口与数据质量。"""

    model_config = ConfigDict(populate_by_name=True)

    compared_symbols: List[str] = Field(..., alias="comparedSymbols", description="参与比较的股票代码")
    shared_evidence: List[Dict[str, Any]] = Field(..., alias="sharedEvidence", description="多股票共同具备的证据")
    divergent_evidence: List[Dict[str, Any]] = Field(..., alias="divergentEvidence", description="多股票之间的证据分歧")
    missing_evidence_by_symbol: Dict[str, List[StockStructureDecisionMissingEvidence]] = Field(
        ...,
        alias="missingEvidenceBySymbol",
        description="按股票分组的缺失比较证据",
    )
    freshness_by_symbol: Dict[str, Dict[str, Any]] = Field(
        ...,
        alias="freshnessBySymbol",
        description="按股票分组的本地证据新鲜度/覆盖摘要",
    )
    confidence_cap: StockSymbolCompareConfidenceCap = Field(
        ...,
        alias="confidenceCap",
        description="比较观察的置信上限",
    )
    observation_boundary: StockSymbolCompareObservationBoundary = Field(
        ...,
        alias="observationBoundary",
        description="观察边界",
    )
    research_next_steps: List[str] = Field(
        ...,
        alias="researchNextSteps",
        description="补齐比较证据的下一步",
    )


class StockStructureDecisionDegradedInput(BaseModel):
    """结构判断中的降级输入说明。"""

    section: str = Field(..., description="受影响的结构面板区段")
    status: Literal["degraded", "unavailable"] = Field(..., description="降级状态")
    reason: str = Field(..., description="降级原因码")


class StockStructureDecisionSourceContext(BaseModel):
    """结构判断的安全来源/钻取上下文。"""

    model_config = ConfigDict(populate_by_name=True)

    source: str = Field(..., description="来源面板标识")
    label: str = Field(..., description="来源面板标签")
    route: str = Field(..., description="来源面板安全路由")
    section: str = Field(..., description="来源面板区段")
    reason: str = Field(..., description="来源上下文原因码")


class StockPeerCorrelationPeerGroup(BaseModel):
    """同业/相关性快照中的本地 peer group 摘要。"""

    model_config = ConfigDict(populate_by_name=True)

    status: Literal["available", "unavailable"] = Field(..., description="peer group 可用性")
    label: Optional[str] = Field(None, description="本地 peer group 标签")
    symbols: List[str] = Field(default_factory=list, description="本地确认的 peer symbols")


class StockPeerCorrelationEvidence(BaseModel):
    """单个 peer 的相关性观察。"""

    model_config = ConfigDict(populate_by_name=True)

    symbol: str = Field(..., description="peer symbol")
    correlation: Optional[float] = Field(None, description="重叠收益序列相关性")
    overlap_days: int = Field(..., alias="overlapDays", description="可比较的重叠日期数量")
    symbol_return_pct: Optional[float] = Field(None, alias="symbolReturnPct", description="研究 symbol 区间涨跌幅")
    peer_return_pct: Optional[float] = Field(None, alias="peerReturnPct", description="peer 区间涨跌幅")
    spread_pct: Optional[float] = Field(None, alias="spreadPct", description="区间涨跌幅差值")
    state: Literal["aligned", "diverging", "insufficient_evidence"] = Field(..., description="单 peer 观察状态")
    summary: str = Field(..., description="面向研究使用的简短观察")


class StockPeerCorrelationSnapshot(BaseModel):
    """单股票同业/相关性快照。"""

    model_config = ConfigDict(populate_by_name=True)

    symbol: str = Field(..., description="研究 symbol")
    peer_group: StockPeerCorrelationPeerGroup = Field(..., alias="peerGroup", description="本地 peer group 摘要")
    correlation_state: Literal["aligned", "diverging", "insufficient_evidence"] = Field(
        ...,
        alias="correlationState",
        description="同业相关性观察状态",
    )
    peer_evidence: List[StockPeerCorrelationEvidence] = Field(
        default_factory=list,
        alias="peerEvidence",
        description="同业相关性证据",
    )
    divergence_evidence: List[StockPeerCorrelationEvidence] = Field(
        default_factory=list,
        alias="divergenceEvidence",
        description="背离证据",
    )
    stale_inputs: List[str] = Field(default_factory=list, alias="staleInputs", description="过期或日期不一致的输入说明")
    missing_inputs: List[str] = Field(default_factory=list, alias="missingInputs", description="缺失输入说明")
    confidence_cap: Literal["low", "medium", "high"] = Field(..., alias="confidenceCap", description="该快照最高可用置信上限")
    observation_boundary: str = Field(..., alias="observationBoundary", description="观察边界说明")
    research_next_steps: List[str] = Field(default_factory=list, alias="researchNextSteps", description="下一步研究路径")


class StockStructureConfidenceCap(BaseModel):
    """结构判断的消费端置信上限。"""

    model_config = ConfigDict(populate_by_name=True)

    value: int = Field(..., ge=0, le=100, description="消费端最高可展示置信分值")
    label: Literal["high", "medium", "low"] = Field(..., description="消费端最高可展示置信标签")
    reasons: List[str] = Field(default_factory=list, description="消费端安全的置信限制原因")


class StockStructureConfidenceState(BaseModel):
    """结构判断的消费端置信状态。"""

    model_config = ConfigDict(populate_by_name=True)

    status: Literal["ready", "evidence limited", "freshness constrained", "source quality limited"] = Field(
        ...,
        description="消费端置信状态",
    )
    label: Literal["high", "medium", "low"] = Field(..., description="消费端最终置信标签")
    reasons: List[str] = Field(default_factory=list, description="消费端安全的状态原因")
    freshness_constrained: bool = Field(..., alias="freshnessConstrained", description="是否受新鲜度限制")
    source_quality_limited: bool = Field(..., alias="sourceQualityLimited", description="是否受来源质量限制")
    thesis_blocked: bool = Field(..., alias="thesisBlocked", description="是否因 thesis eligibility 阻断")


class StockStructureDecisionResponse(BaseModel):
    """单股票结构判断响应。"""

    model_config = ConfigDict(populate_by_name=True)

    schema_version: str = Field(..., alias="schemaVersion", description="API 响应 schema 版本")
    ticker: str = Field(..., description="股票代码")
    symbol: str = Field(..., description="显式归一化股票代码")
    structure_state: str = Field(..., alias="structureState", description="结构状态")
    confidence: Literal["high", "medium", "low"] = Field(..., description="结构判断置信度")
    confidence_cap: Optional[StockStructureConfidenceCap] = Field(
        None,
        alias="confidenceCap",
        description="由证据覆盖约束得到的消费端置信上限",
    )
    confidence_state: Optional[StockStructureConfidenceState] = Field(
        None,
        alias="confidenceState",
        description="由证据覆盖约束得到的消费端置信状态",
    )
    component_scores: Dict[str, int] = Field(..., alias="componentScores", description="组件分数")
    explanation: Dict[str, Any] = Field(..., description="结构说明")
    research_notes: Dict[str, List[str]] = Field(..., alias="researchNotes", description="研究观察备注")
    key_levels: List[Dict[str, Any]] = Field(..., alias="keyLevels", description="仅观察型关键位置")
    evidence_notes: List[str] = Field(..., alias="evidenceNotes", description="结构证据观察")
    risk_observations: List[str] = Field(..., alias="riskObservations", description="风险与失效观察")
    evidence_gaps: List[str] = Field(..., alias="evidenceGaps", description="面向消费者的证据缺口")
    data_quality: StockStructureDecisionDataQuality = Field(..., alias="dataQuality", description="输入数据质量")
    missing_evidence: List[StockStructureDecisionMissingEvidence] = Field(
        ...,
        alias="missingEvidence",
        description="缺失证据列表",
    )
    degraded_inputs: List[StockStructureDecisionDegradedInput] = Field(
        ...,
        alias="degradedInputs",
        description="降级输入说明",
    )
    peer_correlation_snapshot: StockPeerCorrelationSnapshot = Field(
        ...,
        alias="peerCorrelationSnapshot",
        description="本地同业/相关性快照",
    )
    consumer_issues: List[Dict[str, str]] = Field(
        ...,
        alias="consumerIssues",
        description="消费者安全问题提示",
    )
    no_advice_disclosure: str = Field(..., alias="noAdviceDisclosure", description="非个性化建议披露")
    observation_only: Literal[True] = Field(..., alias="observationOnly", description="仅观察型结构阅读")
    decision_grade: Literal[False] = Field(..., alias="decisionGrade", description="不输出决策等级")
    source_context: Optional[StockStructureDecisionSourceContext] = Field(
        None,
        alias="sourceContext",
        description="可选的来源/钻取上下文",
    )
    drilldown_links: List[StockStructureDecisionSourceContext] = Field(
        ...,
        alias="drilldownLinks",
        description="安全的来源/钻取路由列表",
    )


class StockStructureDecisionBatchRequest(BaseModel):
    """批量股票结构判断请求。"""

    model_config = ConfigDict(populate_by_name=True)

    stock_codes: List[str] = Field(
        ...,
        alias="stockCodes",
        min_length=1,
        max_length=100,
        description="股票代码列表",
    )
    benchmark: Optional[str] = Field(None, description="可选比较基准代码")
    max_items: Optional[int] = Field(
        None,
        alias="maxItems",
        ge=1,
        le=50,
        description="本次最多评估的股票数量",
    )


class StockStructureDecisionBatchItemResponse(StockStructureDecisionResponse):
    """批量结构判断中的单股票项。"""

    comparative_context: Optional[StockStructureDecisionComparativeContext] = Field(
        None,
        alias="comparativeContext",
        description="比较上下文；缺少基准证据时显式不可用",
    )


class StockStructureDecisionBatchResponse(BaseModel):
    """批量股票结构判断响应。"""

    model_config = ConfigDict(populate_by_name=True)

    schema_version: str = Field(..., alias="schemaVersion", description="API 响应 schema 版本")
    items: List[StockStructureDecisionBatchItemResponse] = Field(..., description="按输入去重后稳定排序的结构判断项")
    aggregate_summary: Dict[str, Any] = Field(..., alias="aggregateSummary", description="批量结构聚合摘要")
    missing_evidence: List[StockStructureDecisionMissingEvidence] = Field(
        ...,
        alias="missingEvidence",
        description="批量层面的缺失证据列表",
    )
    data_quality: Dict[str, Any] = Field(..., alias="dataQuality", description="批量层面的数据质量摘要")
    symbol_compare_evidence_packet: StockSymbolCompareEvidencePacket = Field(
        ...,
        alias="symbolCompareEvidencePacket",
        description="多股票比较证据包；仅描述证据覆盖、分歧和数据质量",
    )
    no_advice_disclosure: str = Field(..., alias="noAdviceDisclosure", description="非个性化建议披露")
