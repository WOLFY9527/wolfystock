# -*- coding: utf-8 -*-
"""
===================================
历史记录相关模型
===================================

职责：
1. 定义历史记录列表和详情模型
2. 定义分析报告完整模型
"""

from typing import Optional, List, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from api.v1.schemas.home_evidence import (
    HOME_ANALYSIS_CONSUMED_EVIDENCE_FIELDS,
    HomeEvidenceCitationFrame,
    HomeEvidenceCoverageFrame,
    HomeResearchReadiness,
    HomeSingleStockEvidencePacket,
    HomeSourceProvenanceFrame,
    IntelligenceReportPacketV2,
    validate_home_evidence_field,
)


def _exclude_none(value: Any) -> bool:
    return value is None


class HistoryItem(BaseModel):
    """历史记录摘要（列表展示用）"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 1234,
                "query_id": "abc123",
                "stock_code": "600519",
                "stock_name": "贵州茅台",
                "company_name": "贵州茅台",
                "report_type": "detailed",
                "sentiment_score": 75,
                "operation_advice": "继续跟踪",
                "created_at": "2024-01-01T12:00:00",
                "generated_at": "2024-01-01T12:01:05Z",
                "is_test": False,
            }
        }
    )

    id: Optional[int] = Field(None, description="分析历史记录主键 ID")
    query_id: str = Field(..., description="分析记录关联 query_id（批量分析时重复）")
    stock_code: str = Field(..., description="股票代码")
    stock_name: Optional[str] = Field(None, description="股票名称")
    company_name: Optional[str] = Field(None, description="公司名称")
    report_type: Optional[str] = Field(None, description="报告类型")
    sentiment_score: Optional[int] = Field(
        None, 
        description="情绪评分 (0-100)",
        ge=0,
        le=100
    )
    operation_advice: Optional[str] = Field(None, description="研究状态")
    created_at: Optional[str] = Field(None, description="创建时间")
    generated_at: Optional[str] = Field(None, description="持久化报告生成时间")
    is_test: bool = Field(False, description="是否为测试/临时历史记录")
    report_quality: Optional[Any] = Field(None, description="历史报告完整性/溯源状态摘要（可选）")


class HistoryListResponse(BaseModel):
    """历史记录列表响应"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total": 100,
                "page": 1,
                "limit": 20,
                "items": [],
            }
        }
    )

    total: int = Field(..., description="总记录数")
    page: int = Field(..., description="当前页码")
    limit: int = Field(..., description="每页数量")
    items: List[HistoryItem] = Field(default_factory=list, description="记录列表")


class DeleteHistoryRequest(BaseModel):
    """删除历史记录请求"""

    record_ids: List[int] = Field(default_factory=list, description="要删除的历史记录主键 ID 列表")
    delete_all: bool = Field(False, description="是否删除当前用户的全部历史记录")


class DeleteHistoryResponse(BaseModel):
    """删除历史记录响应"""

    deleted: int = Field(..., description="实际删除的历史记录数量")


class NewsIntelItem(BaseModel):
    """新闻情报条目"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "公司发布业绩快报，营收同比增长 20%",
                "snippet": "公司公告显示，季度营收同比增长 20%...",
                "url": "https://example.com/news/123",
            }
        }
    )

    title: str = Field(..., description="新闻标题")
    snippet: str = Field("", description="新闻摘要（最多200字）")
    url: str = Field(..., description="新闻链接")


class NewsIntelResponse(BaseModel):
    """新闻情报响应"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total": 2,
                "items": [],
            }
        }
    )

    total: int = Field(..., description="新闻条数")
    items: List[NewsIntelItem] = Field(default_factory=list, description="新闻列表")


class ReportMeta(BaseModel):
    """报告元信息"""

    model_config = ConfigDict(protected_namespaces=("model_validate", "model_dump"))

    id: Optional[int] = Field(None, description="分析历史记录主键 ID（仅历史报告有此字段）")
    query_id: str = Field(..., description="分析记录关联 query_id（批量分析时重复）")
    stock_code: str = Field(..., description="股票代码")
    stock_name: Optional[str] = Field(None, description="股票名称")
    company_name: Optional[str] = Field(None, description="公司名称")
    report_type: Optional[str] = Field(None, description="报告类型")
    report_language: Optional[str] = Field(None, description="报告输出语言（zh/en）")
    created_at: Optional[str] = Field(None, description="创建时间")
    market_timestamp: Optional[str] = Field(None, description="市场行情时间（ISO 8601, aware）")
    market_session_date: Optional[str] = Field(None, description="市场会话日期（YYYY-MM-DD）")
    news_published_at: Optional[str] = Field(None, description="新闻发布时间（ISO 8601, aware）")
    report_generated_at: Optional[str] = Field(None, description="报告生成时间（ISO 8601, aware）")
    is_test: bool = Field(False, description="是否为测试/临时历史记录")
    current_price: Optional[float] = Field(None, description="分析时股价")
    change_pct: Optional[float] = Field(None, description="分析时涨跌幅(%)")
    model_used: Optional[str] = Field(None, description="分析使用的 LLM 模型")
    researchReadiness: Optional[HomeResearchReadiness] = Field(None, description="研究就绪度投影（可选）")
    evidenceCoverageFrame: Optional[HomeEvidenceCoverageFrame] = Field(None, description="证据覆盖框架（可选）")
    singleStockEvidencePacket: Optional[HomeSingleStockEvidencePacket] = Field(None, description="单票证据包（可选）")
    evidenceCitationFrame: Optional[HomeEvidenceCitationFrame] = Field(
        None,
        description="Home 证据引用框架（可选）",
        exclude_if=_exclude_none,
    )
    sourceProvenanceFrame: Optional[HomeSourceProvenanceFrame] = Field(
        None,
        description="Home 来源溯源框架（可选）",
        exclude_if=_exclude_none,
    )
    intelligencePacket: Optional[IntelligenceReportPacketV2] = Field(
        None,
        description="Intelligence Report Engine v2 结构化研究包（可选）",
        exclude_if=_exclude_none,
    )


class ReportSummary(BaseModel):
    """报告概览区"""
    
    analysis_summary: Optional[str] = Field(None, description="关键结论")
    operation_advice: Optional[str] = Field(None, description="研究状态")
    trend_prediction: Optional[str] = Field(None, description="趋势预测")
    sentiment_score: Optional[int] = Field(
        None, 
        description="情绪评分 (0-100)",
        ge=0,
        le=100
    )
    sentiment_label: Optional[str] = Field(None, description="情绪标签")


class ReportStrategy(BaseModel):
    """关键价位区"""
    
    ideal_buy: Optional[str] = Field(None, description="关键价位参考")
    secondary_buy: Optional[str] = Field(None, description="参考区间")
    stop_loss: Optional[str] = Field(None, description="风险边界")
    take_profit: Optional[str] = Field(None, description="收益阈值")


class ReportDetails(BaseModel):
    """报告详情区"""
    
    news_content: Optional[str] = Field(None, description="新闻摘要")
    raw_result: Optional[Any] = Field(None, description="原始分析结果（JSON）")
    analysis_result: Optional[Any] = Field(None, description="结构化分析结果（兼容明细恢复）")
    raw_ai_response: Optional[Any] = Field(None, description="原始 AI 响应（如有）")
    context_snapshot: Optional[Any] = Field(None, description="分析时上下文快照（JSON）")
    standard_report: Optional[Any] = Field(None, description="统一标准报告数据结构（JSON）")
    data_quality_report: Optional[Any] = Field(None, description="研究关键数据质量报告（可选）")
    financial_report: Optional[Any] = Field(None, description="结构化财报摘要（来自 fundamental_context）")
    dividend_metrics: Optional[Any] = Field(None, description="结构化分红指标（含 TTM 口径）")
    analysis_result: Optional[Any] = Field(None, description="结构化分析结果（API 恢复镜像）")

    @model_validator(mode="after")
    def _hydrate_analysis_result_from_raw_result(self) -> "ReportDetails":
        if self.analysis_result is None and isinstance(self.raw_result, dict):
            analysis_result = self.raw_result.get("analysis_result")
            if analysis_result is not None:
                self.analysis_result = analysis_result
        return self


class HistoryReportDetails(BaseModel):
    """历史详情 API 安全投影，不暴露持久化 raw/debug 容器。"""

    news_content: Optional[str] = Field(None, description="新闻摘要")
    analysis_result: Optional[Any] = Field(None, description="结构化分析结果（API 恢复镜像）")
    standard_report: Optional[Any] = Field(None, description="统一标准报告安全投影（JSON）")
    data_quality_report: Optional[Any] = Field(None, description="研究关键数据质量报告（可选）")
    financial_report: Optional[Any] = Field(None, description="结构化财报摘要（来自 fundamental_context）")
    dividend_metrics: Optional[Any] = Field(None, description="结构化分红指标（含 TTM 口径）")


class AnalysisReport(BaseModel):
    """完整分析报告"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "meta": {
                    "query_id": "abc123",
                    "stock_code": "600519",
                    "stock_name": "贵州茅台",
                    "report_type": "detailed",
                    "report_language": "zh",
                    "created_at": "2024-01-01T12:00:00",
                },
                "summary": {
                    "analysis_summary": "技术面偏正向，继续跟踪证据边界",
                    "operation_advice": "继续跟踪",
                    "trend_prediction": "看多",
                    "sentiment_score": 75,
                    "sentiment_label": "乐观",
                },
                "strategy": {
                    "ideal_buy": "1800.00",
                    "secondary_buy": "1750.00",
                    "stop_loss": "1700.00",
                    "take_profit": "2000.00",
                },
                "details": None,
            }
        }
    )

    meta: ReportMeta = Field(..., description="元信息")
    summary: ReportSummary = Field(..., description="概览区")
    strategy: Optional[ReportStrategy] = Field(None, description="关键价位区")
    details: Optional[ReportDetails] = Field(None, description="详情区")
    decision_trace: Optional[Any] = Field(None, description="研究溯源元数据（可选）")
    data_quality_report: Optional[Any] = Field(None, description="研究关键数据质量报告（可选）")
    report_quality: Optional[Any] = Field(None, description="报告完整性/溯源状态摘要（可选）")
    researchReadiness: Optional[HomeResearchReadiness] = Field(None, description="研究就绪度投影（可选）")
    evidenceCoverageFrame: Optional[HomeEvidenceCoverageFrame] = Field(None, description="证据覆盖框架（可选）")
    singleStockEvidencePacket: Optional[HomeSingleStockEvidencePacket] = Field(None, description="单票证据包（可选）")
    evidenceCitationFrame: Optional[HomeEvidenceCitationFrame] = Field(
        None,
        description="Home 证据引用框架（可选）",
        exclude_if=_exclude_none,
    )
    sourceProvenanceFrame: Optional[HomeSourceProvenanceFrame] = Field(
        None,
        description="Home 来源溯源框架（可选）",
        exclude_if=_exclude_none,
    )
    intelligencePacket: Optional[IntelligenceReportPacketV2] = Field(
        None,
        description="Intelligence Report Engine v2 结构化研究包（可选）",
        exclude_if=_exclude_none,
    )

    @model_validator(mode="after")
    def _hydrate_home_evidence_contracts(self) -> "AnalysisReport":
        analysis_result = None
        if self.details is not None and hasattr(self.details, "analysis_result"):
            analysis_result = getattr(self.details, "analysis_result")
        elif isinstance(self.details, dict):
            analysis_result = self.details.get("analysis_result")

        if not isinstance(analysis_result, dict):
            return self

        for field_name in HOME_ANALYSIS_CONSUMED_EVIDENCE_FIELDS:
            if getattr(self, field_name) is not None:
                continue
            candidate = analysis_result.get(field_name)
            if candidate is not None:
                setattr(self, field_name, validate_home_evidence_field(field_name, candidate))

        if isinstance(self.meta, ReportMeta):
            for field_name in HOME_ANALYSIS_CONSUMED_EVIDENCE_FIELDS:
                if getattr(self.meta, field_name) is None:
                    setattr(self.meta, field_name, getattr(self, field_name))

        return self


class HistoryAnalysisReport(AnalysisReport):
    """历史详情 API 响应模型，复用报告主体但收窄 details 投影。"""

    details: Optional[HistoryReportDetails] = Field(None, description="详情区")


class MarkdownReportResponse(BaseModel):
    """Markdown 格式报告响应"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "content": "# 📊 贵州茅台 (600519) 分析报告\n\n> 分析日期：**2024-01-01**\n\n...",
            }
        }
    )

    content: str = Field(..., description="Markdown 格式的完整报告内容")
