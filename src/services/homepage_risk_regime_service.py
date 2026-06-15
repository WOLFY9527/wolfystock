# -*- coding: utf-8 -*-
"""Pure service that emits a bounded homepage risk-regime contract."""

from __future__ import annotations

from api.v1.schemas.homepage_risk_regime import (
    HOMEPAGE_RISK_REGIME_DEFAULT_AS_OF,
    HOMEPAGE_RISK_REGIME_NO_ADVICE_DISCLOSURE,
    HOMEPAGE_RISK_REGIME_SCHEMA_VERSION,
    HomepageMarketPricingItem,
    HomepageRiskDataQuality,
    HomepageRiskEvidenceQualitySummary,
    HomepageRiskRegimeContradiction,
    HomepageRiskRegimeEvidence,
    HomepageRiskRegimeSnapshot,
    HomepageRiskSignal,
)


def _signal(
    *,
    state: str,
    label: str,
    summary: str,
    affected_variables: tuple[str, ...],
    evidence_quality: str = "needs_confirmation",
    watch_points: tuple[str, ...],
) -> HomepageRiskSignal:
    return HomepageRiskSignal(
        state=state,
        label=label,
        summary=summary,
        affectedVariables=list(affected_variables),
        evidenceQuality=evidence_quality,
        watchPoints=list(watch_points),
    )


_EVIDENCE = (
    HomepageRiskRegimeEvidence(
        key="rates_curve",
        label="利率曲线",
        observation="长端利率回落，短端预期仍有摇摆。",
        implication="风险偏好改善，但证据仍需确认。",
        evidenceQuality="needs_confirmation",
    ),
    HomepageRiskRegimeEvidence(
        key="equity_volatility",
        label="权益波动",
        observation="权益波动压力边际回落。",
        implication="风险资产环境偏有利。",
        evidenceQuality="needs_confirmation",
    ),
    HomepageRiskRegimeEvidence(
        key="defensive_demand",
        label="防御需求",
        observation="黄金需求仍偏强，防御需求上升。",
        implication="交叉资产信号存在分歧。",
        evidenceQuality="mixed",
    ),
)

_CONTRADICTIONS = (
    HomepageRiskRegimeContradiction(
        key="gold_vs_equity",
        label="黄金与权益",
        observation="黄金安全需求偏强，同时权益波动回落。",
        whyItMatters="这意味着风险偏好改善仍需更多交叉验证。",
        evidenceQuality="mixed",
    ),
)

_MARKET_PRICING = (
    HomepageMarketPricingItem(
        key="fed_policy_path",
        label="联储路径预期",
        affectedVariables=["政策利率预期", "两年期利率", "美元方向"],
        pricingLanguage="市场似乎计入降息预期升温，同时保留加息风险尾部。",
        implication="利率压力缓和时，风险偏好改善更容易延续。",
        evidenceQuality="needs_confirmation",
        watchPoints=["通胀读数", "政策表述"],
    ),
    HomepageMarketPricingItem(
        key="treasury_curve",
        label="美债曲线",
        affectedVariables=["两年期利率", "十年期利率", "期限利差"],
        pricingLanguage="曲线移动显示增长与政策预期仍在重新定价。",
        implication="风险偏好中性，方向需要等待利率确认。",
        evidenceQuality="needs_confirmation",
        watchPoints=["长端利率", "期限利差"],
    ),
    HomepageMarketPricingItem(
        key="inflation_pressure",
        label="通胀压力",
        affectedVariables=["通胀预期", "实际利率", "商品价格"],
        pricingLanguage="通胀压力未完全解除，市场对政策宽松保持折扣。",
        implication="若通胀压力回升，风险资产环境可能承压。",
        evidenceQuality="needs_confirmation",
        watchPoints=["核心通胀", "能源价格"],
    ),
    HomepageMarketPricingItem(
        key="dollar_direction",
        label="美元方向",
        affectedVariables=["美元指数", "离岸流动性", "新兴市场压力"],
        pricingLanguage="美元方向偏弱时，风险资产支持通常改善。",
        implication="当前信号指向风险资产环境偏有利。",
        evidenceQuality="needs_confirmation",
        watchPoints=["美元反弹", "实际利率"],
    ),
    HomepageMarketPricingItem(
        key="oil_risk_premium",
        label="油价风险溢价",
        affectedVariables=["油价", "地缘风险溢价", "通胀预期"],
        pricingLanguage="油价包含一定地缘风险溢价。",
        implication="能源上行会削弱风险偏好改善的质量。",
        evidenceQuality="mixed",
        watchPoints=["供应扰动", "运输风险"],
    ),
    HomepageMarketPricingItem(
        key="gold_safe_haven",
        label="黄金安全需求",
        affectedVariables=["黄金", "实际利率", "避险需求"],
        pricingLanguage="黄金需求偏强，说明防御需求上升。",
        implication="交叉资产信号存在分歧。",
        evidenceQuality="mixed",
        watchPoints=["实际利率", "地缘风险"],
    ),
    HomepageMarketPricingItem(
        key="equity_volatility",
        label="权益波动",
        affectedVariables=["权益波动率", "风险溢价", "流动性"],
        pricingLanguage="权益波动降温时，市场对风险资产压力的计入下降。",
        implication="风险资产环境偏有利。",
        evidenceQuality="needs_confirmation",
        watchPoints=["波动回升", "流动性变化"],
    ),
    HomepageMarketPricingItem(
        key="risk_asset_support",
        label="风险资产支持",
        affectedVariables=["信用利差", "成长风格", "加密资产"],
        pricingLanguage="风险资产支持改善，但尚未形成单边确认。",
        implication="风险偏好改善，证据仍需确认。",
        evidenceQuality="needs_confirmation",
        watchPoints=["信用利差", "成长风格延续"],
    ),
    HomepageMarketPricingItem(
        key="defensive_demand",
        label="防御需求",
        affectedVariables=["防御板块", "黄金", "美元"],
        pricingLanguage="防御需求没有完全消退，仍在对冲宏观不确定性。",
        implication="风险偏好中性，交叉资产信号存在分歧。",
        evidenceQuality="mixed",
        watchPoints=["防御板块相对强弱", "黄金需求"],
    ),
)


class HomepageRiskRegimeService:
    """Emit static cross-asset market backdrop without runtime dependencies."""

    def build_snapshot(self) -> HomepageRiskRegimeSnapshot:
        return HomepageRiskRegimeSnapshot(
            schemaVersion=HOMEPAGE_RISK_REGIME_SCHEMA_VERSION,
            asOf=HOMEPAGE_RISK_REGIME_DEFAULT_AS_OF,
            regime="mixed",
            regimeLabel="风险偏好改善但存在分歧",
            summary="风险资产环境偏有利，但防御需求上升，证据仍需确认。",
            evidence=list(_EVIDENCE),
            contradictions=list(_CONTRADICTIONS),
            marketPricing=list(_MARKET_PRICING),
            ratesPricing=_signal(
                state="supportive",
                label="利率定价",
                summary="降息预期升温有助于风险偏好改善。",
                affected_variables=("政策利率预期", "短端利率", "期限利差"),
                watch_points=("通胀读数", "政策表述"),
            ),
            volatilitySignal=_signal(
                state="supportive",
                label="波动信号",
                summary="权益波动降温，风险资产环境偏有利。",
                affected_variables=("权益波动率", "风险溢价"),
                watch_points=("波动回升", "流动性变化"),
            ),
            dollarSignal=_signal(
                state="supportive",
                label="美元信号",
                summary="美元走弱通常减轻风险资产压力。",
                affected_variables=("美元指数", "离岸流动性"),
                watch_points=("美元反弹", "实际利率"),
            ),
            creditSignal=_signal(
                state="neutral",
                label="信用信号",
                summary="信用压力未显著扩散，风险偏好中性。",
                affected_variables=("信用利差", "融资条件"),
                watch_points=("信用利差", "流动性变化"),
            ),
            commoditySignal=_signal(
                state="mixed",
                label="商品信号",
                summary="油价风险溢价与黄金需求同时存在，信号分歧。",
                affected_variables=("油价", "黄金", "通胀预期"),
                evidence_quality="mixed",
                watch_points=("能源价格", "地缘风险"),
            ),
            cryptoSignal=_signal(
                state="neutral",
                label="加密资产信号",
                summary="高波动风险资产支持有限，证据仍需确认。",
                affected_variables=("加密资产", "流动性偏好"),
                watch_points=("流动性变化", "风险偏好延续"),
            ),
            equityStyleSignal=_signal(
                state="supportive",
                label="权益风格信号",
                summary="成长与周期偏好改善时，风险资产环境偏有利。",
                affected_variables=("成长风格", "周期风格"),
                watch_points=("风格轮动", "盈利预期"),
            ),
            defensiveVsOffensiveSignal=_signal(
                state="mixed",
                label="防御与进攻信号",
                summary="进攻线索改善，但防御需求上升。",
                affected_variables=("防御板块", "进攻板块", "黄金"),
                evidence_quality="mixed",
                watch_points=("防御板块相对强弱", "黄金需求"),
            ),
            watchPoints=[
                "通胀读数是否缓和",
                "长端利率是否继续回落",
                "美元是否重新走强",
                "黄金需求是否降温",
                "权益波动是否回升",
            ],
            evidenceQuality=HomepageRiskEvidenceQualitySummary(
                state="mixed",
                label="证据仍需确认",
                summary="利率、美元与波动支持改善，但黄金和油价显示防御需求上升。",
            ),
            dataQuality=HomepageRiskDataQuality(
                status="partial",
                label="静态合约样本",
                available=True,
                summary="固定样本用于首页合约开发，不代表实时市场。",
            ),
            noAdviceDisclosure=HOMEPAGE_RISK_REGIME_NO_ADVICE_DISCLOSURE,
        )


__all__ = [
    "HOMEPAGE_RISK_REGIME_DEFAULT_AS_OF",
    "HOMEPAGE_RISK_REGIME_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_RISK_REGIME_SCHEMA_VERSION",
    "HomepageRiskRegimeService",
]
