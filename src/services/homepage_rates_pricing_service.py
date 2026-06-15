# -*- coding: utf-8 -*-
"""Pure service that emits the homepage Rates Pricing contract."""

from __future__ import annotations

from api.v1.schemas.homepage_rates_pricing import (
    HOMEPAGE_RATES_PRICING_DEFAULT_AS_OF,
    HOMEPAGE_RATES_PRICING_NO_ADVICE_DISCLOSURE,
    HOMEPAGE_RATES_PRICING_SCHEMA_VERSION,
    HomepageRatesAssetImplication,
    HomepageRatesPolicyExpectation,
    HomepageRatesPricingModeSummary,
    HomepageRatesPricingSnapshot,
    HomepageRatesQualitySummary,
    HomepageRatesSignal,
)


def _signal(
    *,
    state: str,
    label: str,
    observation: str,
    implication: str,
    evidence_quality: str,
) -> HomepageRatesSignal:
    return HomepageRatesSignal(
        state=state,
        label=label,
        observation=observation,
        marketBackdropImplication=implication,
        evidenceQuality=evidence_quality,
    )


def _asset_implication(
    *,
    state: str,
    label: str,
    observation: str,
    sensitivity: str,
) -> HomepageRatesAssetImplication:
    return HomepageRatesAssetImplication(
        state=state,
        label=label,
        observation=observation,
        sensitivity=sensitivity,
    )


class HomepageRatesPricingService:
    """Build deterministic rates-pricing observations without runtime dependencies."""

    def build_snapshot(self) -> HomepageRatesPricingSnapshot:
        return HomepageRatesPricingSnapshot(
            schemaVersion=HOMEPAGE_RATES_PRICING_SCHEMA_VERSION,
            asOf=HOMEPAGE_RATES_PRICING_DEFAULT_AS_OF,
            pricingMode=HomepageRatesPricingModeSummary(
                mode="proxy_only",
                label="代理口径",
                fedFuturesPricing="unavailable",
                oisPricing="unavailable",
                summary="未纳入 Fed futures 或 OIS 曲线，仅用利率、曲线和通胀线索刻画背景。",
            ),
            policyExpectation=HomepageRatesPolicyExpectation(
                bias="uncertain",
                label="政策路径待确认",
                pricingAuthority="proxy_only",
                observation="短端利率与政策表述可能分歧，当前不能视为真实政策定价。",
                missingEvidence=[
                    "Fed futures 曲线未接入",
                    "OIS 曲线未接入",
                    "会议概率分布未接入",
                ],
            ),
            ratePathSummary=_signal(
                state="mixed",
                label="利率路径混合",
                observation="长端资金成本与短端政策预期需要分开观察。",
                implication="利率背景尚未形成单一方向，风险偏好需要交叉确认。",
                evidence_quality="needs_confirmation",
            ),
            curveSignal=_signal(
                state="watch",
                label="曲线压力观察",
                observation="期限曲线仍是经济预期和政策约束之间的关键压力线索。",
                implication="若曲线压力重新升高，权益估值和信用背景可能承压。",
                evidence_quality="proxy_observation",
            ),
            realYieldSignal=_signal(
                state="restrictive",
                label="实际利率约束",
                observation="实际利率压力对久期敏感资产仍有约束意义。",
                implication="实际利率回落前，成长风格的背景改善质量仍需复核。",
                evidence_quality="needs_confirmation",
            ),
            inflationPressure=_signal(
                state="watch",
                label="通胀压力观察",
                observation="能源与通胀预期线索会影响政策路径的可解释性。",
                implication="通胀压力若升温，利率背景可能转向更紧约束。",
                evidence_quality="mixed",
            ),
            equityImplication=_asset_implication(
                state="mixed",
                label="权益估值敏感",
                observation="权益背景取决于长端利率、实际利率和盈利线索是否一致。",
                sensitivity="成长和久期资产对利率下行更敏感，但需要广度确认。",
            ),
            dollarImplication=_asset_implication(
                state="watch",
                label="美元压力线索",
                observation="若实际利率与政策预期偏紧，美元压力可能保持韧性。",
                sensitivity="美元方向需要结合全球流动性与风险偏好同步观察。",
            ),
            goldImplication=_asset_implication(
                state="mixed",
                label="黄金分歧线索",
                observation="黄金同时受实际利率和防御需求影响，单一利率线索不足以解释。",
                sensitivity="实际利率回落与防御需求变化需要同时观察。",
            ),
            watchPoints=[
                "短端利率是否继续摇摆",
                "长端利率是否重新上行",
                "期限曲线压力是否扩大",
                "实际利率是否回落",
                "通胀预期是否升温",
                "美元压力是否转强",
                "黄金与权益是否继续分歧",
            ],
            evidenceQuality=HomepageRatesQualitySummary(
                state="proxy_observation",
                label="代理观察",
                summary="证据来自静态利率背景样本，不包含真实政策定价。",
            ),
            dataQuality=HomepageRatesQualitySummary(
                state="partial",
                label="静态合约样本",
                summary="固定样本用于首页合约开发，不代表当前市场数据。",
            ),
            noAdviceDisclosure=HOMEPAGE_RATES_PRICING_NO_ADVICE_DISCLOSURE,
        )


__all__ = [
    "HOMEPAGE_RATES_PRICING_DEFAULT_AS_OF",
    "HOMEPAGE_RATES_PRICING_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_RATES_PRICING_SCHEMA_VERSION",
    "HomepageRatesPricingService",
]
