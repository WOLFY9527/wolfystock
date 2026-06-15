# -*- coding: utf-8 -*-
"""Pure service that emits the homepage Volatility Positioning contract."""

from __future__ import annotations

from api.v1.schemas.homepage_volatility_positioning import (
    HOMEPAGE_VOLATILITY_POSITIONING_DEFAULT_AS_OF,
    HOMEPAGE_VOLATILITY_POSITIONING_NO_ADVICE_DISCLOSURE,
    HOMEPAGE_VOLATILITY_POSITIONING_SCHEMA_VERSION,
    HomepageOptionsDemandProxy,
    HomepageVolatilityContradictionSignal,
    HomepageVolatilityDataQuality,
    HomepageVolatilityPositioningSnapshot,
    HomepageVolatilityPressureSummary,
    HomepageVolatilityQualitySummary,
    HomepageVolatilityRegimeSummary,
    HomepageVolatilityRiskAppetiteImplication,
)


def _pressure(
    *,
    pressure: str,
    label: str,
    observation: str,
    authority: str,
    implication: str,
    evidence_quality: str,
) -> HomepageVolatilityPressureSummary:
    return HomepageVolatilityPressureSummary(
        pressure=pressure,
        label=label,
        observation=observation,
        authority=authority,
        marketBackdropImplication=implication,
        evidenceQuality=evidence_quality,
    )


class HomepageVolatilityPositioningService:
    """Build deterministic volatility positioning observations without runtime dependencies."""

    def build_snapshot(self) -> HomepageVolatilityPositioningSnapshot:
        return HomepageVolatilityPositioningSnapshot(
            schemaVersion=HOMEPAGE_VOLATILITY_POSITIONING_SCHEMA_VERSION,
            asOf=HOMEPAGE_VOLATILITY_POSITIONING_DEFAULT_AS_OF,
            volatilityRegime=HomepageVolatilityRegimeSummary(
                state="mixed",
                label="波动压力混合",
                summary="权益压力边际缓和，但利率波动与尾部风险线索仍需交叉确认。",
                evidenceQuality="proxy_observation",
            ),
            equityVolatility=_pressure(
                pressure="moderate",
                label="权益波动代理",
                observation="权益波动压力处于观察区间，尚不能视为恐慌完全消退。",
                authority="proxy_only",
                implication="风险偏好改善需要广度、信用和流动性线索同步确认。",
                evidence_quality="proxy_observation",
            ),
            rateVolatility=_pressure(
                pressure="elevated",
                label="利率波动压力",
                observation="利率波动仍可能放大久期资产和估值敏感资产的背景压力。",
                authority="proxy_only",
                implication="若利率波动继续升高，权益风险偏好改善质量可能转弱。",
                evidence_quality="needs_confirmation",
            ),
            skewOrTailRisk=_pressure(
                pressure="mixed",
                label="偏斜与尾部风险",
                observation="尾部保护需求无法通过权威期权链确认，仅保留代理观察。",
                authority="proxy_only",
                implication="尾部风险线索未解除前，单一波动降温信号不宜过度解释。",
                evidence_quality="mixed",
            ),
            optionsDemandProxy=HomepageOptionsDemandProxy(
                authority="proxy_only",
                optionChainAuthority="unavailable",
                label="期权需求代理",
                observation="未接入权威期权链，期权需求只能作为间接背景线索。",
                proxySignals=[
                    "权益波动压力变化",
                    "尾部保护需求线索",
                    "利率波动压力变化",
                ],
                missingEvidence=[
                    "authoritative option-chain evidence unavailable",
                    "dealer positioning evidence unavailable",
                    "intraday options-flow evidence unavailable",
                ],
                evidenceQuality="proxy_observation",
            ),
            riskAppetiteImplication=HomepageVolatilityRiskAppetiteImplication(
                state="mixed",
                label="风险偏好待确认",
                observation="权益波动降温与利率波动压力并存，风险偏好方向仍需确认。",
                implication="更适合作为首页观察背景，而非方向性结论。",
                evidenceQuality="mixed",
            ),
            contradictionSignals=[
                HomepageVolatilityContradictionSignal(
                    key="equity_vs_rate_volatility",
                    label="权益与利率波动分歧",
                    observation="权益波动压力缓和，但利率波动仍偏高。",
                    whyItMatters="这会削弱风险偏好改善的可解释性。",
                    evidenceQuality="mixed",
                ),
                HomepageVolatilityContradictionSignal(
                    key="tail_risk_without_chain",
                    label="尾部风险证据不足",
                    observation="尾部保护需求缺少权威期权链确认。",
                    whyItMatters="缺少直接证据时只能保留代理观察。",
                    evidenceQuality="needs_confirmation",
                ),
            ],
            watchPoints=[
                "权益波动压力是否重新升高",
                "利率波动是否继续放大",
                "尾部保护需求是否被直接证据确认",
                "信用压力是否与波动压力共振",
                "市场广度是否支持风险偏好改善",
                "美元与实际利率是否同步施压",
            ],
            evidenceQuality=HomepageVolatilityQualitySummary(
                state="proxy_observation",
                label="代理观察",
                summary="波动定位仅使用静态代理线索，不包含权威期权链或期权成交流。",
            ),
            dataQuality=HomepageVolatilityDataQuality(
                state="partial",
                label="静态合约样本",
                available=True,
                summary="固定样本用于首页合约开发，不代表当前市场数据。",
            ),
            noAdviceDisclosure=HOMEPAGE_VOLATILITY_POSITIONING_NO_ADVICE_DISCLOSURE,
        )


__all__ = [
    "HOMEPAGE_VOLATILITY_POSITIONING_DEFAULT_AS_OF",
    "HOMEPAGE_VOLATILITY_POSITIONING_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_VOLATILITY_POSITIONING_SCHEMA_VERSION",
    "HomepageVolatilityPositioningService",
]
