# -*- coding: utf-8 -*-
"""Build deterministic homepage research priorities without runtime coupling."""

from __future__ import annotations

from api.v1.schemas.homepage_research_priorities import (
    HOMEPAGE_RESEARCH_PRIORITIES_DEFAULT_AS_OF,
    HOMEPAGE_RESEARCH_PRIORITIES_NO_ADVICE_DISCLOSURE,
    HomepageResearchPrioritiesContract,
    HomepageResearchPriority,
    HomepageResearchQuality,
)


EXPECTED_HOMEPAGE_RESEARCH_PRIORITY_LEVELS: tuple[str, ...] = (
    "今日重点观察",
    "优先复核",
    "研究队列",
)

_RESEARCH_PRIORITIES: tuple[HomepageResearchPriority, ...] = (
    HomepageResearchPriority(
        priorityLevel="今日重点观察",
        theme="观察主题：市场广度与情绪同步性",
        whyNow="主要指数与扩散线索需要放在同一视角复核，避免单一价格变化主导判断。",
        evidenceStatus="证据增强",
        supportingSignals=[
            "宽基表现差异扩大",
            "风险偏好线索出现分化",
            "参与活跃度需要连续观察",
        ],
        missingConfirmation=[
            "确认扩散线索是否延续",
            "复核波动变化是否收敛",
        ],
        relatedEvents=[
            "重要公告窗口",
            "市场情绪再定价",
        ],
        relatedMacroDrivers=[
            "利率预期变化",
            "流动性节奏观察",
        ],
        reviewModule="复核方向：市场脉冲",
    ),
    HomepageResearchPriority(
        priorityLevel="优先复核",
        theme="观察主题：资金流与主题持续性",
        whyNow="资金方向与主题热度需要交叉复核，重点确认短期变化是否具备连续证据。",
        evidenceStatus="需要确认",
        supportingSignals=[
            "主题热度排序变化",
            "资金分布出现轮动",
        ],
        missingConfirmation=[
            "确认资金方向是否稳定",
            "复核主题扩散范围",
        ],
        relatedEvents=[
            "行业催化更新",
            "财报信息窗口",
        ],
        relatedMacroDrivers=[
            "风险偏好变化",
            "汇率与利率扰动",
        ],
        reviewModule="复核方向：资金与主题",
    ),
    HomepageResearchPriority(
        priorityLevel="研究队列",
        theme="观察主题：证据缺口与资料补齐",
        whyNow="部分研究线索仍缺少确认材料，适合先进入队列等待证据增强。",
        evidenceStatus="证据不足",
        supportingSignals=[
            "公开资料覆盖仍待补齐",
            "事件影响路径需要复核",
        ],
        missingConfirmation=[
            "补齐相关事件时间线",
            "确认宏观驱动是否仍有效",
        ],
        relatedEvents=[
            "后续数据披露",
            "政策与会议日程",
        ],
        relatedMacroDrivers=[
            "增长预期观察",
            "资金面边际变化",
        ],
        reviewModule="复核方向：证据补齐",
    ),
)


class HomepageResearchPrioritiesService:
    """Emit a static public research-support contract for the homepage cockpit."""

    def build_contract(self) -> HomepageResearchPrioritiesContract:
        return HomepageResearchPrioritiesContract(
            asOf=HOMEPAGE_RESEARCH_PRIORITIES_DEFAULT_AS_OF,
            researchPriorities=list(_RESEARCH_PRIORITIES),
            evidenceQuality=HomepageResearchQuality(
                status="证据增强",
                summary="今日重点观察已按公开研究线索整理，仍需复核方向确认。",
            ),
            dataQuality=HomepageResearchQuality(
                status="需要确认",
                summary="使用固定研究支持样例，不包含来源细节或后台字段。",
            ),
            noAdviceDisclosure=HOMEPAGE_RESEARCH_PRIORITIES_NO_ADVICE_DISCLOSURE,
        )


__all__ = [
    "EXPECTED_HOMEPAGE_RESEARCH_PRIORITY_LEVELS",
    "HomepageResearchPrioritiesService",
]
