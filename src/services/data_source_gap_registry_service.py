# -*- coding: utf-8 -*-
"""Static data source gap registry projection.

The registry is intentionally inert: it does not read credentials, inspect the
environment, call provider runtimes, hydrate data, mutate cache, or write to
storage. It summarizes owned readiness facts and known integration blockers.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any


DATA_SOURCE_GAP_REGISTRY_CONTRACT_VERSION = "data_source_gap_registry_v1"


@dataclass(frozen=True, slots=True)
class DataSourceSurfaceImpact:
    surface_key: str
    consumer_label: str
    impact_state: str
    impact_reason: str
    affected_capability: str
    next_evidence_step: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "surfaceKey": self.surface_key,
            "consumerLabel": self.consumer_label,
            "impactState": self.impact_state,
            "impactReason": self.impact_reason,
            "affectedCapability": self.affected_capability,
            "nextEvidenceStep": self.next_evidence_step,
        }


@dataclass(frozen=True, slots=True)
class DataSourceGapRegistryFamily:
    family_key: str
    consumer_label: str
    status: str
    authority_state: str
    freshness_state: str
    entitlement_or_licensing_blocker: str | None
    integration_blocker: str | None
    source_evidence_state: str
    next_integration_step: str
    provider_hydration_allowed: bool
    score_trading_authority_allowed: bool
    consumer_safe_description: str
    surface_impact_matrix: tuple[DataSourceSurfaceImpact, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "familyKey": self.family_key,
            "consumerLabel": self.consumer_label,
            "status": self.status,
            "authorityState": self.authority_state,
            "freshnessState": self.freshness_state,
            "entitlementOrLicensingBlocker": self.entitlement_or_licensing_blocker,
            "integrationBlocker": self.integration_blocker,
            "sourceEvidenceState": self.source_evidence_state,
            "nextIntegrationStep": self.next_integration_step,
            "providerHydrationAllowed": self.provider_hydration_allowed,
            "scoreTradingAuthorityAllowed": self.score_trading_authority_allowed,
            "consumerSafeDescription": self.consumer_safe_description,
            "surfaceImpactMatrix": [
                impact.to_dict() for impact in self.surface_impact_matrix
            ],
        }


def _impact(
    surface_key: str,
    consumer_label: str,
    impact_state: str,
    impact_reason: str,
    affected_capability: str,
    next_evidence_step: str,
) -> DataSourceSurfaceImpact:
    return DataSourceSurfaceImpact(
        surface_key=surface_key,
        consumer_label=consumer_label,
        impact_state=impact_state,
        impact_reason=impact_reason,
        affected_capability=affected_capability,
        next_evidence_step=next_evidence_step,
    )


_FAMILIES: tuple[DataSourceGapRegistryFamily, ...] = (
    DataSourceGapRegistryFamily(
        family_key="stock_quote_spine",
        consumer_label="Stock Quote Spine",
        status="partial",
        authority_state="blocked",
        freshness_state="delayed",
        entitlement_or_licensing_blocker=None,
        integration_blocker="Durable quote/OHLCV snapshots and unified as-of lineage are still missing.",
        source_evidence_state="fragmented_runtime_evidence",
        next_integration_step="Land bounded quote and OHLCV snapshot storage with authority metadata.",
        provider_hydration_allowed=True,
        score_trading_authority_allowed=False,
        consumer_safe_description=(
            "Quote and OHLCV paths exist, but they are not yet a durable professional spine."
        ),
        surface_impact_matrix=(
            _impact(
                "scanner",
                "Scanner",
                "degraded",
                "报价、日线和成交量血缘不统一，候选池只能保守解释缺口。",
                "候选发现、成交量过滤、空跑阻断桶",
                "补齐有界报价和日线快照，并记录来源权限、时效和覆盖状态。",
            ),
            _impact(
                "watchlist",
                "Watchlist",
                "degraded",
                "保存标的不能从分散报价路径推断行级新鲜度。",
                "行级价格、更新时间、研究状态",
                "让 watchlist row packet 引用明确的报价/日线快照 ID。",
            ),
            _impact(
                "stock_detail",
                "Stock Detail",
                "degraded",
                "个股研究包缺少统一报价、历史和 as-of 血缘。",
                "个股价格、趋势、结构研究输入",
                "把报价、历史和证据引用合并为最小研究包。",
            ),
            _impact(
                "portfolio",
                "Portfolio",
                "degraded",
                "组合估值不能把价格来源、时效和 FX 血缘一起证明。",
                "持仓估值可信度、P&L 读数说明",
                "接入价格和 FX lineage 后再提升估值置信说明。",
            ),
            _impact(
                "backtest_parameter_sweep",
                "Backtest / Parameter Sweep",
                "observation-only",
                "历史 bars 的来源、调整基准和可复现快照仍不完整。",
                "研究级回测数据边界、参数扫读回边界",
                "补齐数据集 ID、调整基准、交易日历和缺失 bars 策略。",
            ),
        ),
    ),
    DataSourceGapRegistryFamily(
        family_key="fundamentals",
        consumer_label="Fundamentals",
        status="partial",
        authority_state="blocked",
        freshness_state="partial",
        entitlement_or_licensing_blocker=None,
        integration_blocker="Point-in-time coverage and restatement-safe normalization are incomplete.",
        source_evidence_state="fragmented_runtime_evidence",
        next_integration_step="Normalize fundamentals, statements, and filing lineage by period and source.",
        provider_hydration_allowed=True,
        score_trading_authority_allowed=False,
        consumer_safe_description=(
            "Fundamental coverage exists in pieces, but period and lineage proof is incomplete."
        ),
        surface_impact_matrix=(
            _impact(
                "stock_detail",
                "Stock Detail",
                "degraded",
                "基本面期间、来源和重述处理未形成统一研究包。",
                "估值、盈利能力、成长性摘要",
                "按期间和来源归一化财务字段并记录缺失项。",
            ),
            _impact(
                "watchlist",
                "Watchlist",
                "planned",
                "行级基本面/事件提示需要先有标准化研究包。",
                "保存标的研究优先级、催化因素摘要",
                "将已验证基本面字段接入 row research packet。",
            ),
            _impact(
                "factor_research",
                "Factor Research",
                "unknown",
                "点时基本面和 forward-return 血缘未证明。",
                "因子暴露、分组研究输入",
                "先补齐点时字段、观察时间和收益标签血缘。",
            ),
        ),
    ),
    DataSourceGapRegistryFamily(
        family_key="etf_index_coverage",
        consumer_label="ETF / Index Coverage",
        status="partial",
        authority_state="blocked",
        freshness_state="delayed",
        entitlement_or_licensing_blocker="Official membership and weight display rights are not yet proven.",
        integration_blocker="Membership, weights, benchmark, and breadth links are not unified.",
        source_evidence_state="fragmented_runtime_evidence",
        next_integration_step="Attach official ETF/index membership snapshots and benchmark mappings.",
        provider_hydration_allowed=True,
        score_trading_authority_allowed=False,
        consumer_safe_description=(
            "ETF and index quotes are partially available, but membership authority is incomplete."
        ),
        surface_impact_matrix=(
            _impact(
                "market_overview",
                "Market Overview",
                "degraded",
                "指数/ETF 报价可作部分市场上下文，成分和权重仍待证明。",
                "宽基市场读数、风险摘要",
                "补齐授权指数/ETF 报价和成分权重快照。",
            ),
            _impact(
                "scanner",
                "Scanner",
                "planned",
                "行业/主题覆盖尚未统一，不能扩展为完整 universe 证据。",
                "行业/主题过滤、候选上下文",
                "接入稳定的成分和行业映射版本。",
            ),
            _impact(
                "portfolio",
                "Portfolio",
                "degraded",
                "基准和成分映射不足会限制组合暴露解释。",
                "基准映射、行业暴露、相对表现说明",
                "补齐 benchmark 与 ETF/index membership lineage。",
            ),
        ),
    ),
    DataSourceGapRegistryFamily(
        family_key="macro_rates",
        consumer_label="Macro / Rates",
        status="observation-only",
        authority_state="observation-only",
        freshness_state="cached",
        entitlement_or_licensing_blocker=None,
        integration_blocker="Durable official macro rows are not yet surfaced as a complete product bundle.",
        source_evidence_state="diagnostic_contract",
        next_integration_step="Persist official macro rows with freshness and coverage metadata.",
        provider_hydration_allowed=True,
        score_trading_authority_allowed=False,
        consumer_safe_description=(
            "Macro and rates readiness is available only as a diagnostic contract today."
        ),
        surface_impact_matrix=(
            _impact(
                "market_overview",
                "Market Overview",
                "observation-only",
                "官方宏观行还不是完整产品数据包，风险读数只能保持边界说明。",
                "利率压力、宏观风险摘要",
                "持久化官方宏观序列并附覆盖和时效状态。",
            ),
            _impact(
                "liquidity_monitor",
                "Liquidity Monitor",
                "observation-only",
                "利率和信用输入仍是诊断契约，不能支撑强流动性结论。",
                "资金面压力、利率传导观察",
                "补齐官方利率/Fed 流动性 bundle 的 freshness 证据。",
            ),
            _impact(
                "scenario_lab",
                "Scenario Lab",
                "planned",
                "情景基线缺少可复现宏观输入引用。",
                "利率冲击、宏观驱动输入",
                "让 durable baseline 引用已存储的宏观快照。",
            ),
        ),
    ),
    DataSourceGapRegistryFamily(
        family_key="fed_liquidity",
        consumer_label="Fed Liquidity",
        status="observation-only",
        authority_state="observation-only",
        freshness_state="cached",
        entitlement_or_licensing_blocker=None,
        integration_blocker="Weekly liquidity rows are not yet persisted as a complete bundle.",
        source_evidence_state="diagnostic_contract",
        next_integration_step="Persist the required liquidity series with coverage and stale-state markers.",
        provider_hydration_allowed=True,
        score_trading_authority_allowed=False,
        consumer_safe_description=(
            "Fed liquidity evidence is contract-shaped, but not yet a durable product spine."
        ),
        surface_impact_matrix=(
            _impact(
                "market_overview",
                "Market Overview",
                "observation-only",
                "周频流动性行尚未作为完整 bundle 持久化。",
                "流动性背景、风险第一读",
                "持久化必需序列并标注滞后状态。",
            ),
            _impact(
                "liquidity_monitor",
                "Liquidity Monitor",
                "degraded",
                "Fed 流动性缺口会限制资金面压力解释。",
                "流动性评分边界、官方风险输入",
                "补齐覆盖、时效和缺失序列说明。",
            ),
            _impact(
                "scenario_lab",
                "Scenario Lab",
                "planned",
                "缺少可复现的 baseline liquidity input。",
                "流动性冲击基线",
                "将流动性快照作为 scenario baseline 引用。",
            ),
        ),
    ),
    DataSourceGapRegistryFamily(
        family_key="credit_stress",
        consumer_label="Credit Stress",
        status="observation-only",
        authority_state="observation-only",
        freshness_state="cached",
        entitlement_or_licensing_blocker=None,
        integration_blocker="A durable credit-stress series is not yet integrated.",
        source_evidence_state="diagnostic_contract",
        next_integration_step="Replace proxy-only context with stored credit-stress series evidence.",
        provider_hydration_allowed=True,
        score_trading_authority_allowed=False,
        consumer_safe_description=(
            "Credit stress is represented through bounded context, not score-grade evidence."
        ),
        surface_impact_matrix=(
            _impact(
                "market_overview",
                "Market Overview",
                "observation-only",
                "信用压力仍是受限上下文，不能提升风险结论强度。",
                "信用压力观察、风险摘要边界",
                "接入持久化信用压力序列和 freshness policy。",
            ),
            _impact(
                "liquidity_monitor",
                "Liquidity Monitor",
                "observation-only",
                "信用压力缺口会限制资金面压力解释。",
                "信用压力观察、流动性边界",
                "补齐来源和覆盖证据后再提升显示状态。",
            ),
        ),
    ),
    DataSourceGapRegistryFamily(
        family_key="vix_volatility",
        consumer_label="VIX / Volatility",
        status="partial",
        authority_state="blocked",
        freshness_state="delayed",
        entitlement_or_licensing_blocker=None,
        integration_blocker="Official volatility rows and authority metadata are not unified.",
        source_evidence_state="fragmented_runtime_evidence",
        next_integration_step="Attach durable official volatility rows and fail-closed freshness gates.",
        provider_hydration_allowed=True,
        score_trading_authority_allowed=False,
        consumer_safe_description=(
            "Volatility evidence exists, but full professional source authority is still blocked."
        ),
        surface_impact_matrix=(
            _impact(
                "market_overview",
                "Market Overview",
                "degraded",
                "波动率证据部分存在，但官方行和权限元数据未统一。",
                "风险温度、波动压力摘要",
                "接入官方波动率行并保持 fail-closed freshness gates。",
            ),
            _impact(
                "liquidity_monitor",
                "Liquidity Monitor",
                "degraded",
                "VIX/波动率缺口会限制压力分层和流动性解释。",
                "波动压力、风险状态",
                "将官方波动率快照纳入风险 bundle。",
            ),
            _impact(
                "scenario_lab",
                "Scenario Lab",
                "planned",
                "情景冲击缺少可复现波动率基线。",
                "波动率冲击输入",
                "让 Scenario baseline 引用已验证波动率快照。",
            ),
        ),
    ),
    DataSourceGapRegistryFamily(
        family_key="breadth_flows_positioning",
        consumer_label="Breadth / Flows / Positioning",
        status="partial",
        authority_state="blocked",
        freshness_state="partial",
        entitlement_or_licensing_blocker="Flow and positioning licensing are not yet proven.",
        integration_blocker="Breadth is partial; flow and positioning families remain incomplete.",
        source_evidence_state="fragmented_runtime_evidence",
        next_integration_step="Separate breadth proof from flow and positioning source reviews.",
        provider_hydration_allowed=True,
        score_trading_authority_allowed=False,
        consumer_safe_description=(
            "Breadth has partial evidence; flow and positioning remain review-bound."
        ),
        surface_impact_matrix=(
            _impact(
                "market_overview",
                "Market Overview",
                "degraded",
                "广度部分可用，资金流和持仓来源仍待评审。",
                "市场参与度、风险摘要",
                "先分离广度证明，再评审资金流和持仓来源。",
            ),
            _impact(
                "scanner",
                "Scanner",
                "planned",
                "广度和成交参与度不能替代 symbol 级报价/历史证据。",
                "候选环境过滤、市场宽度背景",
                "接入覆盖分母和 symbol 级输入后再影响候选解释。",
            ),
            _impact(
                "liquidity_monitor",
                "Liquidity Monitor",
                "observation-only",
                "资金流/持仓未授权时只能作为观察边界。",
                "资金流压力、持仓观察",
                "完成授权来源和 freshness 评审。",
            ),
            _impact(
                "scenario_lab",
                "Scenario Lab",
                "planned",
                "baseline driver 中的广度/资金流输入缺少 durable refs。",
                "参与度与资金流冲击输入",
                "让情景基线引用已验证快照或保持缺失。",
            ),
        ),
    ),
    DataSourceGapRegistryFamily(
        family_key="options_chains",
        consumer_label="Options Chains",
        status="unauthorized",
        authority_state="unauthorized",
        freshness_state="unavailable",
        entitlement_or_licensing_blocker=(
            "Options-chain access, display, storage, and decision-use rights are not proven."
        ),
        integration_blocker="No authorized live or delayed chain store is integrated.",
        source_evidence_state="rights_unproven",
        next_integration_step="Attach an entitlement proof bundle before chain promotion.",
        provider_hydration_allowed=False,
        score_trading_authority_allowed=False,
        consumer_safe_description=(
            "Options chains remain unavailable until authorized chain evidence exists."
        ),
        surface_impact_matrix=(
            _impact(
                "options_lab",
                "Options Lab",
                "blocked",
                "授权期权链、展示权、存储权和字段覆盖未证明。",
                "链、IV、Greeks、OI、成交量观察",
                "先补齐权益证明包和字段覆盖证据。",
            ),
            _impact(
                "stock_detail",
                "Stock Detail",
                "unknown",
                "个股页不能从缺失期权链推断期权结构。",
                "标的期权观察入口",
                "仅在授权链路通过后再接入观察摘要。",
            ),
            _impact(
                "scenario_lab",
                "Scenario Lab",
                "planned",
                "期权链未授权时不得成为情景 baseline 输入。",
                "期权敏感度情景输入",
                "保持缺失，直到授权链和方法证据齐备。",
            ),
        ),
    ),
    DataSourceGapRegistryFamily(
        family_key="options_strategy_analytics",
        consumer_label="Options Strategy Analytics",
        status="blocked",
        authority_state="unauthorized",
        freshness_state="unavailable",
        entitlement_or_licensing_blocker=(
            "Authorized chain inputs and historical replay rights are not proven."
        ),
        integration_blocker="Strategy analytics cannot graduate before chain authority and history exist.",
        source_evidence_state="rights_unproven",
        next_integration_step="Prove authorized chain, history, and methodology inputs first.",
        provider_hydration_allowed=False,
        score_trading_authority_allowed=False,
        consumer_safe_description=(
            "Options strategy analytics remain blocked by missing authorized inputs."
        ),
        surface_impact_matrix=(
            _impact(
                "options_lab",
                "Options Lab",
                "blocked",
                "策略分析不能先于授权链、历史数据和方法输入毕业。",
                "策略结构观察、历史回放边界",
                "先证明授权链、历史链和方法版本。",
            ),
            _impact(
                "backtest_parameter_sweep",
                "Backtest / Parameter Sweep",
                "blocked",
                "没有点时期权历史链和权益证明，不能形成期权历史研究输出。",
                "期权历史研究边界",
                "补齐历史链、权利和回放规则后再评估。",
            ),
        ),
    ),
    DataSourceGapRegistryFamily(
        family_key="gamma_dealer_positioning",
        consumer_label="Gamma / Dealer Positioning",
        status="blocked",
        authority_state="unauthorized",
        freshness_state="unavailable",
        entitlement_or_licensing_blocker=(
            "Options rights, methodology approval, and positioning evidence are not proven."
        ),
        integration_blocker="No approved exposure methodology or rights-backed input set is integrated.",
        source_evidence_state="rights_unproven",
        next_integration_step="Approve rights, inputs, and methodology before exposing gamma-family outputs.",
        provider_hydration_allowed=False,
        score_trading_authority_allowed=False,
        consumer_safe_description=(
            "Gamma, GEX, vanna, charm, and dealer positioning remain blocked."
        ),
        surface_impact_matrix=(
            _impact(
                "options_lab",
                "Options Lab",
                "blocked",
                "Gamma 家族和 dealer positioning 缺少授权输入、持仓假设和方法批准。",
                "Gamma/GEX/vanna/charm/dealer positioning 观察",
                "完成权利、字段覆盖、符号假设和方法版本评审。",
            ),
            _impact(
                "market_overview",
                "Market Overview",
                "unknown",
                "未证明的期权结构不能进入市场风险第一读。",
                "期权结构风险背景",
                "在 Options Lab 方法通过前保持未知。",
            ),
            _impact(
                "scenario_lab",
                "Scenario Lab",
                "blocked",
                "dealer/gamma 输入缺失时不能构成情景基线驱动。",
                "Gamma 情景驱动",
                "保持 blocked，直到授权输入和方法证据存在。",
            ),
        ),
    ),
    DataSourceGapRegistryFamily(
        family_key="backtest_dataset_lineage",
        consumer_label="Backtest Dataset Lineage",
        status="observation-only",
        authority_state="observation-only",
        freshness_state="unknown",
        entitlement_or_licensing_blocker=None,
        integration_blocker="Dataset identity, adjusted basis, calendar, and PIT membership remain incomplete.",
        source_evidence_state="diagnostic_contract",
        next_integration_step="Persist dataset IDs, adjusted-basis evidence, and reproducibility manifests.",
        provider_hydration_allowed=False,
        score_trading_authority_allowed=False,
        consumer_safe_description=(
            "Backtest readback is research-useful, but professional dataset lineage is incomplete."
        ),
        surface_impact_matrix=(
            _impact(
                "backtest_parameter_sweep",
                "Backtest / Parameter Sweep",
                "observation-only",
                "数据集身份、调整基准、交易日历和 PIT membership 不完整。",
                "回测结果可信边界、参数扫读回",
                "补齐 dataset ID、adjusted basis、calendar 和 reproducibility manifest。",
            ),
            _impact(
                "factor_research",
                "Factor Research",
                "observation-only",
                "因子面板和 forward-return 血缘缺失时只能诊断研究边界。",
                "因子 IC、分组收益、长短组合研究边界",
                "建立 factor panel lineage、as-of join 和 forward-return manifest。",
            ),
        ),
    ),
    DataSourceGapRegistryFamily(
        family_key="scenario_baselines",
        consumer_label="Scenario Baselines",
        status="planned",
        authority_state="planned",
        freshness_state="unknown",
        entitlement_or_licensing_blocker=None,
        integration_blocker="Durable baseline snapshot storage is not yet integrated.",
        source_evidence_state="not_integrated",
        next_integration_step="Store baseline snapshot IDs for market and portfolio scenario inputs.",
        provider_hydration_allowed=False,
        score_trading_authority_allowed=False,
        consumer_safe_description=(
            "Scenario baselines are planned, but stored baseline inputs are not integrated."
        ),
        surface_impact_matrix=(
            _impact(
                "scenario_lab",
                "Scenario Lab",
                "planned",
                "存储化 baseline snapshot 尚未接入，常规路径仍偏 request/snapshot 驱动。",
                "基线复现、市场/组合冲击输入",
                "存储 baseline snapshot IDs 并附输入 freshness/authority 摘要。",
            ),
            _impact(
                "evidence_harness",
                "Evidence Harness",
                "planned",
                "target environment 证据需要引用可脱敏的 baseline artifact。",
                "目标环境基线证据",
                "生成面向用户的证据摘要，仅保留可公开解释的信息。",
            ),
        ),
    ),
    DataSourceGapRegistryFamily(
        family_key="portfolio_valuation_lineage",
        consumer_label="Portfolio Valuation Lineage",
        status="partial",
        authority_state="blocked",
        freshness_state="partial",
        entitlement_or_licensing_blocker=None,
        integration_blocker="Price source, FX freshness, benchmark, and factor lineage remain incomplete.",
        source_evidence_state="fragmented_runtime_evidence",
        next_integration_step="Persist price, FX, valuation, benchmark, and factor lineage together.",
        provider_hydration_allowed=True,
        score_trading_authority_allowed=False,
        consumer_safe_description=(
            "Portfolio valuation is partially traced, but source lineage still needs hardening."
        ),
        surface_impact_matrix=(
            _impact(
                "portfolio",
                "Portfolio",
                "degraded",
                "价格来源、FX 时效、估值快照和分析 readiness 仍不完整。",
                "持仓估值置信度、风险/暴露读数",
                "持久化 price、FX、valuation、benchmark 和 factor lineage。",
            ),
            _impact(
                "scenario_lab",
                "Scenario Lab",
                "planned",
                "组合情景输入缺少稳定估值和 FX baseline 引用。",
                "组合冲击基线",
                "让 Scenario baseline 引用组合估值快照 ID。",
            ),
            _impact(
                "backtest_parameter_sweep",
                "Backtest / Parameter Sweep",
                "unknown",
                "组合分配回测需要单独 accounting/benchmark gate，当前不应推断。",
                "组合分配研究边界",
                "先保留未知，等待独立组合回测合同。",
            ),
        ),
    ),
)


def _summary(families: tuple[DataSourceGapRegistryFamily, ...]) -> dict[str, int]:
    counts = Counter(family.status for family in families)
    return {
        "totalFamilies": len(families),
        "readyCount": counts.get("ready", 0),
        "partialCount": counts.get("partial", 0),
        "missingCount": counts.get("missing", 0),
        "blockedCount": counts.get("blocked", 0),
        "unauthorizedCount": counts.get("unauthorized", 0),
        "staleCount": counts.get("stale", 0),
        "observationOnlyCount": counts.get("observation-only", 0),
        "plannedCount": counts.get("planned", 0),
        "providerHydrationAllowedCount": sum(
            1 for family in families if family.provider_hydration_allowed
        ),
        "scoreTradingAuthorityAllowedCount": sum(
            1 for family in families if family.score_trading_authority_allowed
        ),
    }


def build_data_source_gap_registry() -> dict[str, Any]:
    """Return a deterministic, fail-closed data-family readiness registry."""

    families = _FAMILIES
    return {
        "contractVersion": DATA_SOURCE_GAP_REGISTRY_CONTRACT_VERSION,
        "diagnosticOnly": True,
        "providerRuntimeCalled": False,
        "networkCallsEnabled": False,
        "scoreAuthorityAllowed": False,
        "summary": _summary(families),
        "families": [family.to_dict() for family in families],
        "metadata": {
            "source": "static_contract_registry",
            "readOnly": True,
            "noExternalCalls": True,
            "mutationEnabled": False,
            "credentialsRead": False,
            "rawProviderPayloadsIncluded": False,
        },
    }


__all__ = [
    "DATA_SOURCE_GAP_REGISTRY_CONTRACT_VERSION",
    "DataSourceSurfaceImpact",
    "DataSourceGapRegistryFamily",
    "build_data_source_gap_registry",
]
