# -*- coding: utf-8 -*-
"""Deterministic liquidity and credit stress service for the homepage cockpit."""

from __future__ import annotations

from api.v1.schemas.homepage_liquidity_credit import (
    HOMEPAGE_LIQUIDITY_CREDIT_DEFAULT_AS_OF,
    HOMEPAGE_LIQUIDITY_CREDIT_NO_ADVICE_DISCLOSURE,
    HOMEPAGE_LIQUIDITY_CREDIT_SCHEMA_VERSION,
    HomepageLiquidityCreditCondition,
    HomepageLiquidityCreditDataQuality,
    HomepageLiquidityCreditEvidenceQuality,
    HomepageLiquidityCreditProxy,
    HomepageLiquidityCreditRiskAssetImplication,
    HomepageLiquidityCreditSnapshot,
)


_LIQUIDITY_CONDITION = HomepageLiquidityCreditCondition(
    state="neutral",
    evidenceState="needs_confirmation",
    label="流动性中性",
    summary="美元、融资压力与国债流动性线索未形成单边压力，当前更适合中性观察。",
)
_CREDIT_STRESS_CONDITION = HomepageLiquidityCreditCondition(
    state="neutral",
    evidenceState="proxy_only",
    label="信用压力待确认",
    summary="仅有代理线索，尚不足以确认信用压力已明显扩散或缓和。",
)
_FUNDING_PRESSURE = HomepageLiquidityCreditProxy(
    key="funding_pressure",
    label="融资压力",
    state="neutral",
    evidenceState="needs_confirmation",
    dataQuality="partial",
    isProxy=True,
    summary="融资压力线索未显示一致紧张背景。",
    interpretation="风险资产背景暂未被融资压力单独压制，但仍需交叉复核。",
)
_HIGH_YIELD_PROXY = HomepageLiquidityCreditProxy(
    key="high_yield_proxy",
    label="高收益信用代理",
    state="neutral",
    evidenceState="proxy_only",
    dataQuality="no_evidence",
    isProxy=True,
    summary="高收益信用压力仅保留代理线索，不展示信用利差结论。",
    interpretation="缺少直接信用利差证据时，只能用于提醒后续复核方向。",
)
_TREASURY_LIQUIDITY_PROXY = HomepageLiquidityCreditProxy(
    key="treasury_liquidity_proxy",
    label="国债流动性代理",
    state="neutral",
    evidenceState="needs_confirmation",
    dataQuality="partial",
    isProxy=True,
    summary="国债流动性代理未给出明确紧张信号。",
    interpretation="若国债流动性转弱，权益估值和高波动资产需要重新观察。",
)
_DOLLAR_LIQUIDITY = HomepageLiquidityCreditProxy(
    key="dollar_liquidity",
    label="美元流动性",
    state="neutral",
    evidenceState="medium",
    dataQuality="partial",
    isProxy=True,
    summary="美元流动性背景偏中性，未构成单独压力来源。",
    interpretation="美元压力若重新升温，跨市场风险偏好通常会更谨慎。",
)
_RISK_ASSET_IMPLICATION = HomepageLiquidityCreditRiskAssetImplication(
    state="neutral",
    label="风险资产中性观察",
    summary="流动性和信用压力条件未形成明确支持或紧张状态。",
    observation="在直接信用利差证据缺位时，风险资产解读应保持观察语气。",
)
_EVIDENCE_QUALITY = HomepageLiquidityCreditEvidenceQuality(
    state="proxy_only",
    label="代理线索",
    summary="当前仅整理代理线索和缺口，不声称覆盖完整信用利差证据。",
)
_DATA_QUALITY = HomepageLiquidityCreditDataQuality(
    state="partial",
    label="证据不完整",
    available=False,
    summary="该合约为固定观察样例，直接信用利差与实时资金条件仍缺失。",
)


class HomepageLiquidityCreditService:
    """Build a static public liquidity-credit contract without runtime dependencies."""

    def build_snapshot(self) -> HomepageLiquidityCreditSnapshot:
        return HomepageLiquidityCreditSnapshot(
            schemaVersion=HOMEPAGE_LIQUIDITY_CREDIT_SCHEMA_VERSION,
            asOf=HOMEPAGE_LIQUIDITY_CREDIT_DEFAULT_AS_OF,
            liquidityCondition=_LIQUIDITY_CONDITION,
            creditStressCondition=_CREDIT_STRESS_CONDITION,
            fundingPressure=_FUNDING_PRESSURE,
            highYieldProxy=_HIGH_YIELD_PROXY,
            treasuryLiquidityProxy=_TREASURY_LIQUIDITY_PROXY,
            dollarLiquidity=_DOLLAR_LIQUIDITY,
            riskAssetImplication=_RISK_ASSET_IMPLICATION,
            evidenceSummary="当前合约仅汇总代理线索，用于观察流动性与信用压力是否支持风险资产背景。",
            missingEvidence=[
                "直接信用利差证据",
                "短端融资压力时间序列",
                "国债市场深度确认",
                "美元资金条件交叉验证",
            ],
            watchPoints=[
                "高收益信用压力是否扩散",
                "美元流动性是否转紧",
                "国债流动性是否恶化",
                "融资压力是否影响高波动资产",
            ],
            evidenceQuality=_EVIDENCE_QUALITY,
            dataQuality=_DATA_QUALITY,
            noAdviceDisclosure=HOMEPAGE_LIQUIDITY_CREDIT_NO_ADVICE_DISCLOSURE,
        )


__all__ = [
    "HOMEPAGE_LIQUIDITY_CREDIT_DEFAULT_AS_OF",
    "HOMEPAGE_LIQUIDITY_CREDIT_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_LIQUIDITY_CREDIT_SCHEMA_VERSION",
    "HomepageLiquidityCreditService",
]
