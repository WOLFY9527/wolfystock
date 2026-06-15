# -*- coding: utf-8 -*-
"""Pure service that emits the homepage Theme Capital Flow contract."""

from __future__ import annotations

from api.v1.schemas.homepage_theme_capital_flow import (
    HOMEPAGE_THEME_CAPITAL_FLOW_DEFAULT_AS_OF,
    HOMEPAGE_THEME_CAPITAL_FLOW_NO_ADVICE_DISCLOSURE,
    HOMEPAGE_THEME_CAPITAL_FLOW_SCHEMA_VERSION,
    HomepageThemeCapitalFlowSnapshot,
    HomepageThemeFlowAggregate,
    HomepageThemeFlowAuthorityDefinition,
    HomepageThemeFlowAuthoritySummary,
    HomepageThemeFlowDataQuality,
    HomepageThemeFlowEvidenceInput,
    HomepageThemeFlowEvidenceQuality,
    HomepageThemeFlowItem,
)


_AUTHORITY_DEFINITIONS = (
    HomepageThemeFlowAuthorityDefinition(
        state="authoritative",
        label="权威资金流",
        meaning="由权威资金流证据支持，可与代理观察分开呈现。",
    ),
    HomepageThemeFlowAuthorityDefinition(
        state="proxy_only",
        label="代理观察",
        meaning="仅由相对强弱、扩散和持续性观察支持，不代表真实资金流。",
    ),
    HomepageThemeFlowAuthorityDefinition(
        state="unavailable",
        label="暂不可用",
        meaning="相关证据本轮未纳入，不能形成方向性资金判断。",
    ),
    HomepageThemeFlowAuthorityDefinition(
        state="no_evidence",
        label="无证据",
        meaning="当前没有可用观察证据，只保留主题占位。",
    ),
)


def _theme(
    *,
    key: str,
    theme: str,
    direction: str,
    conviction: str,
    evidence_quality: str,
    data_quality: str = "partial",
    observation: str,
    watch_point: str,
) -> HomepageThemeFlowItem:
    return HomepageThemeFlowItem(
        key=key,
        theme=theme,
        direction=direction,
        flowAuthority="proxy_only",
        proxyOnly=True,
        conviction=conviction,
        evidenceQuality=evidence_quality,
        dataQuality=data_quality,
        observation=observation,
        watchPoint=watch_point,
    )


_INFLOW_THEMES = (
    _theme(
        key="ai_infrastructure",
        theme="AI infrastructure",
        direction="inflow",
        conviction="medium",
        evidence_quality="proxy_observation",
        observation="代理观察显示算力基础设施关注度较高，但不代表真实资金流。",
        watch_point="继续观察扩散是否从核心硬件延伸到配套环节。",
    ),
    _theme(
        key="semiconductors",
        theme="semiconductors",
        direction="inflow",
        conviction="medium",
        evidence_quality="proxy_observation",
        observation="半导体相对强弱与主题延续性较突出，仍属观察型代理证据。",
        watch_point="关注强势是否由少数龙头扩展到设备与材料。",
    ),
    _theme(
        key="data_centers",
        theme="data centers",
        direction="inflow",
        conviction="medium",
        evidence_quality="needs_confirmation",
        observation="数据中心链条保持较高关注，证据仍需用后续广度确认。",
        watch_point="观察机柜、电力与运营环节是否同步改善。",
    ),
    _theme(
        key="power_equipment",
        theme="power equipment",
        direction="inflow",
        conviction="medium",
        evidence_quality="needs_confirmation",
        observation="电力设备受算力与电网投资线索支撑，当前仅可视为代理观察。",
        watch_point="关注订单线索与主题扩散是否保持一致。",
    ),
    _theme(
        key="liquid_cooling",
        theme="liquid cooling",
        direction="inflow",
        conviction="low",
        evidence_quality="needs_confirmation",
        observation="液冷主题随算力链延伸出现关注，但样本广度仍偏有限。",
        watch_point="观察关注度是否从概念扩展到业绩验证环节。",
    ),
)

_OUTFLOW_THEMES = (
    _theme(
        key="real_estate",
        theme="real estate",
        direction="outflow",
        conviction="medium",
        evidence_quality="proxy_observation",
        observation="房地产相对表现偏弱，代理观察显示资金关注不足。",
        watch_point="观察政策线索是否改善板块广度。",
    ),
    _theme(
        key="consumer_defensive",
        theme="consumer defensive",
        direction="outflow",
        conviction="low",
        evidence_quality="needs_confirmation",
        observation="防御消费关注度不稳定，可能反映风险偏好切换。",
        watch_point="关注防御需求是否重新抬升。",
    ),
    _theme(
        key="financials",
        theme="financials",
        direction="outflow",
        conviction="low",
        evidence_quality="mixed",
        observation="金融主题线索分化，当前代理证据不足以形成强方向。",
        watch_point="观察利率、信用与成交活跃度是否给出一致线索。",
    ),
)

_STRENGTHENING_THEMES = (
    _theme(
        key="software",
        theme="software",
        direction="strengthening",
        conviction="medium",
        evidence_quality="needs_confirmation",
        observation="软件主题随 AI 应用与效率线索改善，仍需确认广度。",
        watch_point="观察应用层与基础软件是否同步走强。",
    ),
    _theme(
        key="cybersecurity",
        theme="cybersecurity",
        direction="strengthening",
        conviction="low",
        evidence_quality="needs_confirmation",
        observation="网络安全关注度温和改善，当前属于观察型代理证据。",
        watch_point="关注预算韧性与软件链条联动。",
    ),
    _theme(
        key="defense",
        theme="defense",
        direction="strengthening",
        conviction="low",
        evidence_quality="mixed",
        observation="国防主题受风险预算与政策线索影响，证据仍有分歧。",
        watch_point="观察强势是否具备持续性而非单日波动。",
    ),
    _theme(
        key="energy",
        theme="energy",
        direction="strengthening",
        conviction="low",
        evidence_quality="mixed",
        observation="能源主题受到价格与供给线索支撑，但周期属性带来分歧。",
        watch_point="关注油气价格与现金流预期是否一致。",
    ),
)

_FADING_THEMES = (
    _theme(
        key="gold_precious_metals",
        theme="gold / precious metals",
        direction="fading",
        conviction="low",
        evidence_quality="mixed",
        observation="贵金属关注度从高位降温，但防御需求未完全消退。",
        watch_point="观察实际利率与避险需求是否重新强化。",
    ),
    _theme(
        key="biotech",
        theme="biotech",
        direction="fading",
        conviction="low",
        evidence_quality="needs_confirmation",
        observation="生物科技主题代理观察偏弱，研究关注仍较分散。",
        watch_point="关注融资环境与临床事件是否改善证据质量。",
    ),
    _theme(
        key="small_cap_growth",
        theme="small-cap growth",
        direction="fading",
        conviction="low",
        evidence_quality="needs_confirmation",
        observation="小盘成长扩散不足，当前仅能作为观察占位。",
        watch_point="观察广度是否从大盘成长扩展到小盘成长。",
    ),
)

_EVIDENCE_INPUTS = (
    HomepageThemeFlowEvidenceInput(
        key="relative_strength",
        label="主题相对强弱",
        authority="proxy_only",
        available=True,
        summary="用于观察主题之间的相对表现，不代表真实资金流。",
    ),
    HomepageThemeFlowEvidenceInput(
        key="breadth_diffusion",
        label="广度与扩散",
        authority="proxy_only",
        available=True,
        summary="用于观察强势是否从少数主题扩展到更多成员。",
    ),
    HomepageThemeFlowEvidenceInput(
        key="authoritative_flow",
        label="权威资金流",
        authority="unavailable",
        available=False,
        summary="本合约未纳入权威资金流证据。",
    ),
    HomepageThemeFlowEvidenceInput(
        key="direct_flow_confirmation",
        label="直接资金流确认",
        authority="no_evidence",
        available=False,
        summary="当前没有直接资金流确认，只保留代理观察口径。",
    ),
)


class HomepageThemeCapitalFlowService:
    """Emit deterministic theme capital-flow observations without runtime dependencies."""

    def build_snapshot(self) -> HomepageThemeCapitalFlowSnapshot:
        return HomepageThemeCapitalFlowSnapshot(
            schemaVersion=HOMEPAGE_THEME_CAPITAL_FLOW_SCHEMA_VERSION,
            asOf=HOMEPAGE_THEME_CAPITAL_FLOW_DEFAULT_AS_OF,
            flowAuthority=HomepageThemeFlowAuthoritySummary(
                status="proxy_only",
                label="仅代理观察",
                summary="当前仅呈现主题相对强弱与扩散观察，不代表真实或权威资金流。",
                authoritativeAvailable=False,
                definitions=list(_AUTHORITY_DEFINITIONS),
            ),
            proxyOnly=True,
            inflowThemes=list(_INFLOW_THEMES),
            outflowThemes=list(_OUTFLOW_THEMES),
            strengtheningThemes=list(_STRENGTHENING_THEMES),
            fadingThemes=list(_FADING_THEMES),
            concentration=HomepageThemeFlowAggregate(
                status="concentrated",
                label="主题集中",
                summary="强势观察集中在 AI 基础设施、半导体和数据中心相关链条。",
                evidenceQuality="proxy_observation",
            ),
            breadth=HomepageThemeFlowAggregate(
                status="selective",
                label="扩散有限",
                summary="广度仍偏选择性，少数主题较强，防御和地产相关线索偏弱。",
                evidenceQuality="needs_confirmation",
            ),
            evidenceInputs=list(_EVIDENCE_INPUTS),
            evidenceQuality=HomepageThemeFlowEvidenceQuality(
                status="proxy_observation",
                label="代理观察",
                summary="证据来自静态相对强弱与扩散占位，仍需后续确认。",
            ),
            dataQuality=HomepageThemeFlowDataQuality(
                status="partial",
                label="静态合约样本",
                available=True,
                summary="固定样本用于首页合约开发，不代表实时市场。",
            ),
            noAdviceDisclosure=HOMEPAGE_THEME_CAPITAL_FLOW_NO_ADVICE_DISCLOSURE,
        )


__all__ = [
    "HOMEPAGE_THEME_CAPITAL_FLOW_DEFAULT_AS_OF",
    "HOMEPAGE_THEME_CAPITAL_FLOW_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_THEME_CAPITAL_FLOW_SCHEMA_VERSION",
    "HomepageThemeCapitalFlowService",
]
