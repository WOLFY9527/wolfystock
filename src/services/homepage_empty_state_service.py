# -*- coding: utf-8 -*-
"""Build bounded homepage empty-state copy without runtime coupling."""

from __future__ import annotations

from api.v1.schemas.homepage_empty_state import (
    HOMEPAGE_EMPTY_STATE_DEFAULT_AS_OF,
    HOMEPAGE_EMPTY_STATE_MODULE_KEYS,
    HOMEPAGE_EMPTY_STATE_NO_ADVICE_DISCLOSURE,
    HomepageEmptyStateContract,
    HomepageEmptyStateCopy,
    HomepageEmptyStateDataQuality,
)


EXPECTED_HOMEPAGE_EMPTY_STATE_MODULE_KEYS = HOMEPAGE_EMPTY_STATE_MODULE_KEYS

_EMPTY_STATE_COPY: tuple[HomepageEmptyStateCopy, ...] = (
    HomepageEmptyStateCopy(
        moduleKey="market_pulse",
        title="市场脉冲待补充",
        message="当前缺少足够市场广度与价格线索，先展示缺省说明。",
        reviewPoint="等待市场状态证据补齐后再复核。",
        state="no_evidence",
    ),
    HomepageEmptyStateCopy(
        moduleKey="money_flow",
        title="资金流线索不足",
        message="当前资金流向证据不完整，仅保留观察占位。",
        reviewPoint="复核资金方向、扩散度与持续性。",
        state="partial",
    ),
    HomepageEmptyStateCopy(
        moduleKey="event_radar",
        title="事件雷达暂无证据",
        message="当前未形成可展示事件摘要，先提示继续观察。",
        reviewPoint="等待公告、日历或新闻证据补齐。",
        state="no_evidence",
    ),
    HomepageEmptyStateCopy(
        moduleKey="personal_summary",
        title="个人摘要未就绪",
        message="当前缺少可公开展示的个人研究摘要。",
        reviewPoint="复核关注列表与研究记录是否完整。",
        state="unavailable",
    ),
    HomepageEmptyStateCopy(
        moduleKey="research_queue",
        title="研究队列为空",
        message="当前没有排队中的研究事项，可先显示空状态。",
        reviewPoint="等待新的研究主题或复核事项加入。",
        state="no_evidence",
    ),
    HomepageEmptyStateCopy(
        moduleKey="public_data_quality",
        title="数据质量待复核",
        message="当前公开数据质量说明不足，先展示谨慎占位。",
        reviewPoint="复核覆盖范围、更新时间与缺口说明。",
        state="partial",
    ),
    HomepageEmptyStateCopy(
        moduleKey="source_freshness",
        title="来源新鲜度待确认",
        message="当前来源更新时间不足以支撑完整展示。",
        reviewPoint="等待来源更新时间与覆盖状态补齐。",
        state="partial",
    ),
    HomepageEmptyStateCopy(
        moduleKey="homepage_intelligence",
        title="首页智能说明就绪",
        message="缺省文案可用于首页模块空状态展示。",
        reviewPoint="仅复核展示口径与模块顺序。",
        state="ready",
    ),
)


class HomepageEmptyStateService:
    """Emit static public copy for homepage module empty states."""

    def build_contract(self) -> HomepageEmptyStateContract:
        return HomepageEmptyStateContract(
            status="ready",
            asOf=HOMEPAGE_EMPTY_STATE_DEFAULT_AS_OF,
            emptyStates=list(_EMPTY_STATE_COPY),
            noAdviceDisclosure=HOMEPAGE_EMPTY_STATE_NO_ADVICE_DISCLOSURE,
            dataQuality=HomepageEmptyStateDataQuality(
                state="ready",
                label="缺省文案已就绪",
                available=True,
                summary="首页模块缺省说明使用固定公开文案，不包含运行细节。",
            ),
        )


__all__ = [
    "EXPECTED_HOMEPAGE_EMPTY_STATE_MODULE_KEYS",
    "HomepageEmptyStateService",
]
