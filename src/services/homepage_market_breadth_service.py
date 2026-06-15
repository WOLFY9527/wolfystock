# -*- coding: utf-8 -*-
"""Deterministic market breadth service for the homepage cockpit."""

from __future__ import annotations

from api.v1.schemas.homepage_market_breadth import (
    HOMEPAGE_MARKET_BREADTH_DEFAULT_AS_OF,
    HOMEPAGE_MARKET_BREADTH_NO_ADVICE_DISCLOSURE,
    HOMEPAGE_MARKET_BREADTH_SCHEMA_VERSION,
    HomepageBreadthAxisState,
    HomepageBreadthDataQuality,
    HomepageBreadthPublicState,
    HomepageBreadthQuality,
    HomepageBreadthRegime,
    HomepageMarketBreadthSnapshot,
)


def _public_state(*, status: str, label: str, summary: str) -> HomepageBreadthPublicState:
    return HomepageBreadthPublicState(status=status, label=label, summary=summary)


def _axis(
    *,
    status: str,
    label: str,
    summary: str,
    evidence_state: str,
) -> HomepageBreadthAxisState:
    return HomepageBreadthAxisState(
        status=status,
        label=label,
        summary=summary,
        evidenceState=evidence_state,
    )


class HomepageMarketBreadthService:
    """Build a static public breadth projection without runtime dependencies."""

    def build_snapshot(self) -> HomepageMarketBreadthSnapshot:
        return HomepageMarketBreadthSnapshot(
            schemaVersion=HOMEPAGE_MARKET_BREADTH_SCHEMA_VERSION,
            asOf=HOMEPAGE_MARKET_BREADTH_DEFAULT_AS_OF,
            breadthRegime=HomepageBreadthRegime(
                status="concentrated",
                label="集中型强度",
                summary="市场强度主要集中在少数主题和权重资产，广度扩散仍需确认。",
            ),
            participationSummary=_public_state(
                status="proxy",
                label="参与率代理观察",
                summary="主题与市值风格显示参与不均衡，缺少上涨家数相对下跌家数的直接确认。",
            ),
            advancingVsDeclining=_axis(
                status="no_evidence",
                label="涨跌家数",
                summary="当前合约不声明涨跌家数结论，该轴保留为缺失证据。",
                evidence_state="no_evidence",
            ),
            leadershipConcentration=_axis(
                status="proxy",
                label="领先集中度",
                summary="强度更偏向少数权重资产，广度是否扩散仍需后续复核。",
                evidence_state="proxy",
            ),
            themeConcentration=_axis(
                status="proxy",
                label="主题集中度",
                summary="主题线索集中在少数方向，尚未形成均衡扩散。",
                evidence_state="proxy",
            ),
            largeCapVsSmallCap=_axis(
                status="proxy",
                label="大盘对小盘",
                summary="大盘线索更明确，小盘参与度仍需补充观察。",
                evidence_state="proxy",
            ),
            growthVsValue=_axis(
                status="proxy",
                label="成长对价值",
                summary="成长风格更突出，价值风格的同步性仍不充分。",
                evidence_state="proxy",
            ),
            offensiveVsDefensive=_axis(
                status="needs_confirmation",
                label="进攻对防御",
                summary="进攻线索存在，但防御需求并未完全消退，需要交叉确认。",
                evidence_state="needs_confirmation",
            ),
            confirmationStatus=_public_state(
                status="proxy",
                label="代理确认",
                summary="当前仅能用代理线索说明参与结构，不能声明广度已被确认。",
            ),
            missingEvidence=[
                "上涨家数相对下跌家数缺少直接确认。",
                "小盘参与度需要补充。",
                "防御与进攻风格的同步性仍需复核。",
            ],
            watchPoints=[
                "少数主题强度是否继续主导。",
                "小盘与非权重资产参与度是否改善。",
                "成长、价值与防御风格是否出现更均衡扩散。",
            ],
            evidenceQuality=HomepageBreadthQuality(
                status="proxy",
                label="代理线索",
                summary="公开静态样本只支持结构观察，不支持确认型广度结论。",
            ),
            dataQuality=HomepageBreadthDataQuality(
                status="partial",
                label="证据部分就绪",
                available=True,
                summary="合约使用固定公开结构样本，直接广度证据仍不完整。",
            ),
            noAdviceDisclosure=HOMEPAGE_MARKET_BREADTH_NO_ADVICE_DISCLOSURE,
        )


__all__ = [
    "HOMEPAGE_MARKET_BREADTH_DEFAULT_AS_OF",
    "HOMEPAGE_MARKET_BREADTH_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_MARKET_BREADTH_SCHEMA_VERSION",
    "HomepageMarketBreadthService",
]
