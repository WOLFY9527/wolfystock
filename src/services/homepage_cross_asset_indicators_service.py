# -*- coding: utf-8 -*-
"""Deterministic cross-asset indicators service for the homepage cockpit."""

from __future__ import annotations

from api.v1.schemas.homepage_cross_asset_indicators import (
    HOMEPAGE_CROSS_ASSET_INDICATORS_DEFAULT_AS_OF,
    HOMEPAGE_CROSS_ASSET_INDICATORS_NO_ADVICE_DISCLOSURE,
    HOMEPAGE_CROSS_ASSET_INDICATORS_SCHEMA_VERSION,
    CrossAssetContradiction,
    CrossAssetDataQuality,
    CrossAssetGroupSummary,
    CrossAssetIndicator,
    CrossAssetQualitySummary,
    HomepageCrossAssetIndicatorsSnapshot,
)


def _indicator(
    *,
    key: str,
    label: str,
    asset_group: str,
    value_label: str,
    state: str,
    evidence_state: str,
    description: str,
    interpretation: str,
    watch_points: tuple[str, ...],
) -> CrossAssetIndicator:
    return CrossAssetIndicator(
        key=key,
        label=label,
        assetGroup=asset_group,
        valueLabel=value_label,
        state=state,
        evidenceState=evidence_state,
        description=description,
        interpretation=interpretation,
        watchPoints=list(watch_points),
    )


def _group(
    *,
    key: str,
    label: str,
    state: str,
    evidence_state: str,
    indicator_keys: tuple[str, ...],
    summary: str,
    watch_points: tuple[str, ...],
) -> CrossAssetGroupSummary:
    return CrossAssetGroupSummary(
        key=key,
        label=label,
        state=state,
        evidenceState=evidence_state,
        indicatorKeys=list(indicator_keys),
        summary=summary,
        watchPoints=list(watch_points),
    )


_INDICATORS = (
    _indicator(
        key="vix",
        label="VIX",
        asset_group="volatility",
        value_label="equity volatility lens",
        state="partial",
        evidence_state="medium",
        description="观察美股权益波动压力是否扩散。",
        interpretation="波动压力温和时，风险偏好背景更稳定。",
        watch_points=("波动率是否回升", "权益广度是否同步"),
    ),
    _indicator(
        key="move",
        label="MOVE",
        asset_group="volatility",
        value_label="unavailable",
        state="unavailable",
        evidence_state="needs_confirmation",
        description="美债波动指标预留占位，当前不展示数值。",
        interpretation="缺少该线索时，利率波动判断需要交叉复核。",
        watch_points=("美债波动补充", "期限利差变化"),
    ),
    _indicator(
        key="us_10y_yield",
        label="10Y yield",
        asset_group="rates",
        value_label="rate backdrop",
        state="partial",
        evidence_state="medium",
        description="十年期收益率用于观察长端资金成本。",
        interpretation="长端利率缓和时，估值敏感资产压力通常减轻。",
        watch_points=("长端利率方向", "实际利率变化"),
    ),
    _indicator(
        key="us_2y_yield",
        label="2Y yield",
        asset_group="rates",
        value_label="policy path lens",
        state="partial",
        evidence_state="medium",
        description="两年期收益率用于观察政策路径预期。",
        interpretation="短端利率摇摆会影响风险偏好的稳定性。",
        watch_points=("短端利率方向", "政策表述变化"),
    ),
    _indicator(
        key="dollar_index",
        label="Dollar Index",
        asset_group="dollar",
        value_label="dollar direction lens",
        state="partial",
        evidence_state="medium",
        description="美元指数用于观察全球流动性压力。",
        interpretation="美元压力缓和时，跨市场风险背景更友好。",
        watch_points=("美元是否转强", "离岸流动性变化"),
    ),
    _indicator(
        key="gold",
        label="Gold",
        asset_group="commodities",
        value_label="defensive demand lens",
        state="partial",
        evidence_state="medium",
        description="黄金用于观察防御需求与实际利率压力。",
        interpretation="黄金偏强可能提示市场仍在保留防御线索。",
        watch_points=("黄金需求强弱", "实际利率变化"),
    ),
    _indicator(
        key="oil",
        label="Oil",
        asset_group="commodities",
        value_label="inflation pressure lens",
        state="partial",
        evidence_state="medium",
        description="油价用于观察通胀压力与供应扰动。",
        interpretation="能源走强会削弱风险背景改善的质量。",
        watch_points=("能源价格方向", "通胀预期变化"),
    ),
    _indicator(
        key="btc",
        label="BTC",
        asset_group="crypto",
        value_label="high beta sentiment lens",
        state="partial",
        evidence_state="weak",
        description="BTC 用于观察高波动资产情绪。",
        interpretation="高波动资产走强可作为风险偏好的辅助线索。",
        watch_points=("流动性变化", "风险偏好延续"),
    ),
    _indicator(
        key="eth",
        label="ETH",
        asset_group="crypto",
        value_label="high beta breadth lens",
        state="partial",
        evidence_state="weak",
        description="ETH 用于观察加密资产内部扩散程度。",
        interpretation="内部扩散改善时，高波动风险偏好更有延续性。",
        watch_points=("内部扩散强弱", "高波动资产分化"),
    ),
    _indicator(
        key="high_yield_credit_proxy",
        label="High-yield credit",
        asset_group="creditProxy",
        value_label="credit stress lens",
        state="no_evidence",
        evidence_state="needs_confirmation",
        description="高收益信用线索用于观察融资压力。",
        interpretation="信用压力若扩散，风险背景需要降级观察。",
        watch_points=("信用利差变化", "融资条件变化"),
    ),
    _indicator(
        key="growth_vs_value",
        label="Growth vs value",
        asset_group="equityStyle",
        value_label="style leadership lens",
        state="partial",
        evidence_state="medium",
        description="成长与价值相对表现用于观察权益风格偏好。",
        interpretation="成长风格占优通常更依赖利率与流动性支持。",
        watch_points=("成长风格延续", "价值风格修复"),
    ),
    _indicator(
        key="large_cap_vs_small_cap",
        label="Large-cap vs small-cap",
        asset_group="equityStyle",
        value_label="size breadth lens",
        state="partial",
        evidence_state="medium",
        description="大盘与小盘相对表现用于观察风险扩散。",
        interpretation="小盘参与改善时，权益风险偏好更均衡。",
        watch_points=("小盘参与度", "权重股集中度"),
    ),
)

_VOLATILITY = _group(
    key="volatility",
    label="波动",
    state="partial",
    evidence_state="medium",
    indicator_keys=("vix", "move"),
    summary="权益波动线索可用，利率波动占位待补充。",
    watch_points=("权益波动回升", "利率波动补充"),
)
_RATES = _group(
    key="rates",
    label="利率",
    state="partial",
    evidence_state="medium",
    indicator_keys=("us_10y_yield", "us_2y_yield"),
    summary="长端与短端利率共同刻画资金成本和政策路径预期。",
    watch_points=("长端利率方向", "短端利率摇摆"),
)
_DOLLAR = _group(
    key="dollar",
    label="美元",
    state="partial",
    evidence_state="medium",
    indicator_keys=("dollar_index",),
    summary="美元方向用于观察全球流动性压力是否缓和。",
    watch_points=("美元是否转强", "离岸流动性变化"),
)
_COMMODITIES = _group(
    key="commodities",
    label="商品",
    state="partial",
    evidence_state="conflicting",
    indicator_keys=("gold", "oil"),
    summary="黄金偏防御，油价偏通胀压力，商品线索存在分歧。",
    watch_points=("黄金需求强弱", "能源价格方向"),
)
_CRYPTO = _group(
    key="crypto",
    label="加密资产",
    state="partial",
    evidence_state="weak",
    indicator_keys=("btc", "eth"),
    summary="加密资产只作为高波动风险偏好的辅助观察。",
    watch_points=("高波动资产分化", "流动性变化"),
)
_CREDIT_PROXY = _group(
    key="creditProxy",
    label="信用代理",
    state="no_evidence",
    evidence_state="needs_confirmation",
    indicator_keys=("high_yield_credit_proxy",),
    summary="信用压力线索当前不足，需要结合公开利差或融资条件复核。",
    watch_points=("信用利差变化", "融资条件变化"),
)
_EQUITY_STYLE = _group(
    key="equityStyle",
    label="权益风格",
    state="partial",
    evidence_state="medium",
    indicator_keys=("growth_vs_value", "large_cap_vs_small_cap"),
    summary="风格和市值扩散用于观察风险偏好是否从权重资产外溢。",
    watch_points=("成长风格延续", "小盘参与度"),
)

_ASSET_GROUPS = (
    _VOLATILITY,
    _RATES,
    _DOLLAR,
    _COMMODITIES,
    _CRYPTO,
    _CREDIT_PROXY,
    _EQUITY_STYLE,
)


class HomepageCrossAssetIndicatorsService:
    """Build a static public cross-asset backdrop without runtime dependencies."""

    def build_snapshot(self) -> HomepageCrossAssetIndicatorsSnapshot:
        return HomepageCrossAssetIndicatorsSnapshot(
            schemaVersion=HOMEPAGE_CROSS_ASSET_INDICATORS_SCHEMA_VERSION,
            asOf=HOMEPAGE_CROSS_ASSET_INDICATORS_DEFAULT_AS_OF,
            indicators=list(_INDICATORS),
            assetGroups=list(_ASSET_GROUPS),
            volatility=_VOLATILITY,
            rates=_RATES,
            dollar=_DOLLAR,
            commodities=_COMMODITIES,
            crypto=_CRYPTO,
            creditProxy=_CREDIT_PROXY,
            equityStyle=_EQUITY_STYLE,
            summary=(
                "当前跨资产背景偏混合：利率与美元压力观察有改善线索，商品与信用线索仍需复核。"
            ),
            contradictions=[
                CrossAssetContradiction(
                    key="gold_vs_risk_assets",
                    label="黄金与风险资产",
                    observation="黄金防御需求仍在，同时高波动资产情绪并未完全转弱。",
                    whyItMatters="这说明市场背景并非单向，需要多资产同步确认。",
                    evidenceState="conflicting",
                ),
                CrossAssetContradiction(
                    key="rates_vs_credit",
                    label="利率与信用",
                    observation="利率线索可观察，但信用压力证据不足。",
                    whyItMatters="缺少信用确认时，风险背景只能保持部分确认。",
                    evidenceState="needs_confirmation",
                ),
            ],
            watchPoints=[
                "VIX 是否回升",
                "MOVE 数据是否补充",
                "十年期与两年期利率是否同向",
                "美元指数是否转强",
                "黄金与油价是否继续分歧",
                "信用压力线索是否补齐",
                "成长与小盘参与是否扩散",
            ],
            evidenceQuality=CrossAssetQualitySummary(
                state="needs_confirmation",
                label="证据需要交叉确认",
                summary="多数指标为静态观察样本，MOVE 与信用线索仍待补充。",
            ),
            dataQuality=CrossAssetDataQuality(
                state="partial",
                label="静态合约样本",
                available=True,
                summary="固定样本用于首页合同开发，不代表当前市场数据。",
            ),
            noAdviceDisclosure=HOMEPAGE_CROSS_ASSET_INDICATORS_NO_ADVICE_DISCLOSURE,
        )


__all__ = [
    "HOMEPAGE_CROSS_ASSET_INDICATORS_DEFAULT_AS_OF",
    "HOMEPAGE_CROSS_ASSET_INDICATORS_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_CROSS_ASSET_INDICATORS_SCHEMA_VERSION",
    "HomepageCrossAssetIndicatorsService",
]
