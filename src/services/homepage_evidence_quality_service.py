# -*- coding: utf-8 -*-
"""Pure service for the homepage evidence-quality projection contract."""

from __future__ import annotations

from api.v1.schemas.homepage_evidence_quality import (
    HOMEPAGE_EVIDENCE_QUALITY_DEFAULT_AS_OF,
    HOMEPAGE_EVIDENCE_QUALITY_NO_ADVICE_DISCLOSURE,
    HOMEPAGE_EVIDENCE_QUALITY_SCHEMA_VERSION,
    HomepageEvidenceDataFreshness,
    HomepageEvidenceDataQuality,
    HomepageEvidenceQualityLabel,
    HomepageEvidenceQualityProjection,
    HomepageEvidenceQualitySection,
)


def _quality(*, state: str, label: str, summary: str) -> HomepageEvidenceQualityLabel:
    return HomepageEvidenceQualityLabel(state=state, label=label, summary=summary)


def _freshness(*, state: str, label: str, summary: str) -> HomepageEvidenceDataFreshness:
    return HomepageEvidenceDataFreshness(state=state, label=label, summary=summary)


_SECTIONS = (
    HomepageEvidenceQualitySection(
        sectionKey="market_structure",
        sectionLabel="市场结构",
        conclusionAllowed=True,
        evidenceQuality=_quality(
            state="strong",
            label="证据较强",
            summary="价格、成交量与市场广度相互确认，结论支持度较高。",
        ),
        evidenceSummary="价格、成交量与市场广度相互确认，适合形成首页背景结论。",
        supportingEvidence=[
            "价格方向与成交活跃度同步改善。",
            "主要指数与市场广度同时提供支持。",
            "波动线索未明显削弱结构判断。",
        ],
        missingEvidence=[],
        conflictingEvidence=[],
        dataFreshness=_freshness(
            state="ready",
            label="证据就绪",
            summary="公开结构线索完整，可用于首页证据说明。",
        ),
        publicConfidenceLabel="公开证据支持较强",
    ),
    HomepageEvidenceQualitySection(
        sectionKey="breadth_confirmation",
        sectionLabel="广度确认",
        conclusionAllowed=True,
        evidenceQuality=_quality(
            state="needs_confirmation",
            label="需要确认",
            summary="价格线索存在，但市场广度尚未确认，结论需要保持克制。",
        ),
        evidenceSummary="价格线索存在，但市场广度尚未确认，需要等待参与率扩散。",
        supportingEvidence=["主要指数方向提供初步支持。"],
        missingEvidence=["上涨参与率仍需进一步确认。", "主题扩散强度尚未形成一致线索。"],
        conflictingEvidence=[],
        dataFreshness=_freshness(
            state="partial",
            label="证据部分就绪",
            summary="广度线索不完整，仅能支持有限结论。",
        ),
        publicConfidenceLabel="公开证据需要确认",
    ),
    HomepageEvidenceQualitySection(
        sectionKey="news_catalyst",
        sectionLabel="新闻催化",
        conclusionAllowed=True,
        evidenceQuality=_quality(
            state="medium",
            label="证据中等",
            summary="新闻催化存在，资金流向尚未确认，适合继续观察。",
        ),
        evidenceSummary="新闻催化存在，资金流向尚未确认，结论支持度为中等。",
        supportingEvidence=["公开事件线索解释了部分短期关注度。"],
        missingEvidence=["资金流向尚未确认。", "成交延续性仍需观察。"],
        conflictingEvidence=[],
        dataFreshness=_freshness(
            state="delayed",
            label="证据延迟",
            summary="事件线索可读，但资金确认存在时间差。",
        ),
        publicConfidenceLabel="公开证据支持中等",
    ),
    HomepageEvidenceQualitySection(
        sectionKey="cross_asset_context",
        sectionLabel="跨资产背景",
        conclusionAllowed=False,
        evidenceQuality=_quality(
            state="conflicting",
            label="证据分歧",
            summary="跨资产信号存在分歧，不能单独支持明确结论。",
        ),
        evidenceSummary="跨资产信号存在分歧，需要结合利率、美元、波动与商品线索复核。",
        supportingEvidence=["部分风险偏好线索改善。"],
        missingEvidence=[],
        conflictingEvidence=[
            "防御需求与风险偏好改善同时出现。",
            "利率、美元与商品线索没有完全同向。",
        ],
        dataFreshness=_freshness(
            state="cached",
            label="证据可复核",
            summary="跨资产背景使用固定公开样本说明，适合作为复核线索。",
        ),
        publicConfidenceLabel="公开证据存在分歧",
    ),
    HomepageEvidenceQualitySection(
        sectionKey="flow_confirmation",
        sectionLabel="资金确认",
        conclusionAllowed=False,
        evidenceQuality=_quality(
            state="weak",
            label="证据偏弱",
            summary="资金确认不足，只能说明当前结论仍需补充证据。",
        ),
        evidenceSummary="资金确认不足，当前只支持观察结论，不支持更强表达。",
        supportingEvidence=[],
        missingEvidence=["资金持续性不足。", "板块间参与度需要进一步确认。"],
        conflictingEvidence=[],
        dataFreshness=_freshness(
            state="no_evidence",
            label="暂无证据",
            summary="资金确认线索不足，首页应显示低支持强度。",
        ),
        publicConfidenceLabel="公开证据偏弱",
    ),
)


class HomepageEvidenceQualityService:
    """Build a deterministic public projection without runtime dependencies."""

    def build_projection(self) -> HomepageEvidenceQualityProjection:
        return HomepageEvidenceQualityProjection(
            schemaVersion=HOMEPAGE_EVIDENCE_QUALITY_SCHEMA_VERSION,
            asOf=HOMEPAGE_EVIDENCE_QUALITY_DEFAULT_AS_OF,
            sections=list(_SECTIONS),
            dataQuality=HomepageEvidenceDataQuality(
                state="partial",
                label="证据质量分层",
                available=True,
                summary="静态公开合约用于说明首页结论支持强度，不代表实时市场。",
            ),
            noAdviceDisclosure=HOMEPAGE_EVIDENCE_QUALITY_NO_ADVICE_DISCLOSURE,
        )


__all__ = [
    "HOMEPAGE_EVIDENCE_QUALITY_DEFAULT_AS_OF",
    "HOMEPAGE_EVIDENCE_QUALITY_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_EVIDENCE_QUALITY_SCHEMA_VERSION",
    "HomepageEvidenceQualityService",
]
