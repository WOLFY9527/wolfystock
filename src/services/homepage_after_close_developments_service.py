# -*- coding: utf-8 -*-
"""Pure service that emits a deterministic homepage after-close developments contract."""

from __future__ import annotations

from api.v1.schemas.homepage_after_close_developments import (
    HOMEPAGE_AFTER_CLOSE_DEVELOPMENTS_DEFAULT_AS_OF,
    HOMEPAGE_AFTER_CLOSE_DEVELOPMENTS_NO_ADVICE_DISCLOSURE,
    HOMEPAGE_AFTER_CLOSE_DEVELOPMENTS_SCHEMA_VERSION,
    HomepageAfterCloseDevelopment,
    HomepageAfterCloseDevelopmentsSnapshot,
    HomepageAfterCloseLatestSession,
    HomepageAfterCloseQuality,
    HomepageAfterCloseSection,
    HomepageAfterCloseSectionItem,
    HomepageAfterCloseWatchPoint,
)


_OVERNIGHT_CONTEXT_ITEMS = (
    HomepageAfterCloseSectionItem(
        key="global_index_reference",
        label="全球指数背景样本",
        basis="sample_proxy",
        evidenceState="sample_proxy",
        observation="固定样本显示海外指数背景可作为次日开盘前研究参考。",
        researchContext="需要把指数背景与利率、美元和商品线索一起观察。",
        watchPoints=["指数广度", "美元方向", "利率曲线"],
    ),
    HomepageAfterCloseSectionItem(
        key="liquidity_calendar",
        label="流动性日历样本",
        basis="sample_proxy",
        evidenceState="sample_proxy",
        observation="资金日历样本提示隔夜流动性环境可能影响开盘前风险偏好。",
        researchContext="研究时关注利率、美元和信用背景是否互相印证。",
        watchPoints=["短端利率", "信用利差", "资金面叙事"],
    ),
)

_FUTURES_TONE_ITEMS = (
    HomepageAfterCloseSectionItem(
        key="index_futures_proxy",
        label="股指期货基调样本",
        basis="sample_proxy",
        evidenceState="sample_proxy",
        observation="期货基调使用固定样本表达方向敏感度，不代表真实盘后报价。",
        researchContext="若后续接入真实数据，应保留样本标记直到证据质量明确。",
        watchPoints=["指数期货方向", "波动率背景", "成交活跃度"],
    ),
)

_EARNINGS_CATALYST_ITEMS = (
    HomepageAfterCloseSectionItem(
        key="megacap_earnings_watch",
        label="大型企业业绩观察样本",
        basis="sample_proxy",
        evidenceState="sample_proxy",
        observation="大型企业业绩样本用于提示财报和指引可能影响指数权重结构。",
        researchContext="观察重点是收入质量、利润率、现金流和行业传导。",
        watchPoints=["收入质量", "利润率变化", "行业传导"],
    ),
    HomepageAfterCloseSectionItem(
        key="ai_capex_disclosure_watch",
        label="AI资本开支披露样本",
        basis="sample_proxy",
        evidenceState="sample_proxy",
        observation="AI资本开支样本用于提示算力链和电力基础设施研究线索。",
        researchContext="需要结合订单能见度、供给约束和现金流质量观察。",
        watchPoints=["资本开支指引", "供应链交付", "电力容量"],
    ),
)

_MACRO_EVENT_ITEMS = (
    HomepageAfterCloseSectionItem(
        key="inflation_calendar_proxy",
        label="通胀日历样本",
        basis="sample_proxy",
        evidenceState="sample_proxy",
        observation="通胀日历样本提示价格数据可能改变利率预期观察框架。",
        researchContext="重点是核心通胀、工资变化和期限利差是否同向。",
        watchPoints=["核心通胀", "工资变化", "期限利差"],
    ),
    HomepageAfterCloseSectionItem(
        key="central_bank_language_proxy",
        label="央行措辞样本",
        basis="sample_proxy",
        evidenceState="sample_proxy",
        observation="央行措辞样本用于标记政策路径研究需要复核。",
        researchContext="观察政策措辞、短端利率和美元方向是否形成一致背景。",
        watchPoints=["政策措辞", "短端利率", "美元方向"],
    ),
)

_GEOPOLITICAL_EVENT_ITEMS = (
    HomepageAfterCloseSectionItem(
        key="energy_shipping_risk_proxy",
        label="能源运输风险样本",
        basis="sample_proxy",
        evidenceState="sample_proxy",
        observation="能源运输风险样本提示油价风险溢价和航运成本需要共同观察。",
        researchContext="研究时区分供应扰动、需求变化和避险情绪来源。",
        watchPoints=["航运通行", "保险成本", "油价波动"],
    ),
)

_COMMODITY_MOVE_ITEMS = (
    HomepageAfterCloseSectionItem(
        key="oil_gold_proxy",
        label="原油与黄金样本",
        basis="sample_proxy",
        evidenceState="sample_proxy",
        observation="商品样本提示能源价格和避险资产可能影响通胀与风险偏好观察。",
        researchContext="需要同时观察油价、黄金和美元是否给出一致信号。",
        watchPoints=["能源价格", "黄金方向", "美元方向"],
    ),
)

_RATES_MOVE_ITEMS = (
    HomepageAfterCloseSectionItem(
        key="rates_overnight_proxy",
        label="隔夜利率样本",
        basis="sample_proxy",
        evidenceState="sample_proxy",
        observation="利率样本提示期限结构可能影响成长估值和金融条件观察。",
        researchContext="研究重点是短端政策预期、长端期限溢价与实际利率。",
        watchPoints=["短端利率", "长端利率", "实际利率"],
    ),
)

_AFTER_CLOSE_DEVELOPMENTS = (
    HomepageAfterCloseDevelopment(
        key="index_futures_proxy",
        label="指数期货背景样本",
        category="futures_tone",
        basis="sample_proxy",
        evidenceState="sample_proxy",
        observation="固定样本用于表达收盘后指数方向观察位，不代表真实盘后数据。",
        researchContext="开盘前需要结合波动率、美元和利率背景复核风险偏好。",
        relatedAssets=["股票指数", "波动率", "美元指数"],
        watchPoints=["指数期货方向", "波动率变化", "美元方向"],
    ),
    HomepageAfterCloseDevelopment(
        key="megacap_earnings_watch",
        label="大型企业业绩催化样本",
        category="earnings_catalyst",
        basis="sample_proxy",
        evidenceState="sample_proxy",
        observation="固定样本用于表达大型企业业绩和指引对指数权重的研究影响。",
        researchContext="观察收入质量、利润率与行业链条是否同步改善。",
        relatedAssets=["大型科技股", "行业ETF", "指数权重股"],
        watchPoints=["收入质量", "利润率", "行业传导"],
    ),
    HomepageAfterCloseDevelopment(
        key="rates_overnight_proxy",
        label="隔夜利率变化样本",
        category="rates_move",
        basis="sample_proxy",
        evidenceState="sample_proxy",
        observation="固定样本用于表达利率曲线变化对估值和融资条件的研究影响。",
        researchContext="关注短端政策预期、长端期限溢价和美元方向是否共振。",
        relatedAssets=["美债曲线", "成长资产", "美元指数"],
        watchPoints=["短端利率", "长端利率", "期限利差"],
    ),
    HomepageAfterCloseDevelopment(
        key="energy_geopolitical_proxy",
        label="能源地缘背景样本",
        category="geopolitical_event",
        basis="sample_proxy",
        evidenceState="sample_proxy",
        observation="固定样本用于表达能源与地缘背景对通胀和避险需求的研究影响。",
        researchContext="需要把油价、航运成本和黄金方向放在同一框架观察。",
        relatedAssets=["原油", "黄金", "航运"],
        watchPoints=["油价波动", "航运通行", "黄金方向"],
    ),
)

_TODAY_WATCH_POINTS = (
    HomepageAfterCloseWatchPoint(
        key="opening_gap_context",
        label="开盘缺口背景",
        basis="sample_proxy",
        evidenceState="sample_proxy",
        observation="开盘前观察样本关注隔夜背景是否形成一致风险偏好。",
        researchContext="用于组织研究问题，不给出方向性执行结论。",
    ),
    HomepageAfterCloseWatchPoint(
        key="macro_asset_alignment",
        label="宏观资产一致性",
        basis="sample_proxy",
        evidenceState="sample_proxy",
        observation="宏观资产样本关注利率、美元、商品和指数是否互相印证。",
        researchContext="若线索冲突，应提高证据复核权重。",
    ),
    HomepageAfterCloseWatchPoint(
        key="earnings_transmission",
        label="业绩传导路径",
        basis="sample_proxy",
        evidenceState="sample_proxy",
        observation="业绩样本关注个股披露是否扩散到行业和主题研究。",
        researchContext="重点是质量、利润率、现金流和行业链条反馈。",
    ),
)


class HomepageAfterCloseDevelopmentsService:
    """Build a static after-close context snapshot without runtime dependencies."""

    def build_snapshot(self) -> HomepageAfterCloseDevelopmentsSnapshot:
        return HomepageAfterCloseDevelopmentsSnapshot(
            schemaVersion=HOMEPAGE_AFTER_CLOSE_DEVELOPMENTS_SCHEMA_VERSION,
            asOf=HOMEPAGE_AFTER_CLOSE_DEVELOPMENTS_DEFAULT_AS_OF,
            latestSession=HomepageAfterCloseLatestSession(
                label="最近常规交易时段",
                regularCloseAt="2026-06-14T20:00:00Z",
                nextRegularOpenAt="2026-06-15T13:30:00Z",
                basis="sample_proxy",
                summary="固定样本用于表达最近收盘到下次开盘之间的观察窗口。",
            ),
            afterCloseDevelopments=list(_AFTER_CLOSE_DEVELOPMENTS),
            overnightContext=HomepageAfterCloseSection(
                state="sample_proxy",
                summary="隔夜背景为固定样本，用于组织开盘前研究问题。",
                items=list(_OVERNIGHT_CONTEXT_ITEMS),
            ),
            futuresTone=HomepageAfterCloseSection(
                state="sample_proxy",
                summary="期货基调为固定样本，不代表真实盘后报价或方向判断。",
                items=list(_FUTURES_TONE_ITEMS),
            ),
            earningsCatalysts=HomepageAfterCloseSection(
                state="sample_proxy",
                summary="业绩催化为固定样本，用于表达财报和指引相关研究线索。",
                items=list(_EARNINGS_CATALYST_ITEMS),
            ),
            macroEvents=HomepageAfterCloseSection(
                state="sample_proxy",
                summary="宏观事件为固定样本，用于表达通胀、就业和政策路径观察。",
                items=list(_MACRO_EVENT_ITEMS),
            ),
            geopoliticalEvents=HomepageAfterCloseSection(
                state="sample_proxy",
                summary="地缘事件为固定样本，用于表达能源、航运和避险背景观察。",
                items=list(_GEOPOLITICAL_EVENT_ITEMS),
            ),
            commodityMoves=HomepageAfterCloseSection(
                state="sample_proxy",
                summary="商品变化为固定样本，用于表达能源与贵金属研究背景。",
                items=list(_COMMODITY_MOVE_ITEMS),
            ),
            ratesMoves=HomepageAfterCloseSection(
                state="sample_proxy",
                summary="利率变化为固定样本，用于表达期限结构与估值背景观察。",
                items=list(_RATES_MOVE_ITEMS),
            ),
            todayWatchPoints=list(_TODAY_WATCH_POINTS),
            evidenceQuality=HomepageAfterCloseQuality(
                state="sample_proxy",
                label="固定样本证据",
                summary="当前输出为合约样本，不声称包含真实收盘后新闻或行情。",
            ),
            dataQuality=HomepageAfterCloseQuality(
                state="sample_proxy",
                label="静态样本数据",
                summary="所有条目均为固定样本或代理表达，不代表当前市场数据。",
            ),
            noAdviceDisclosure=HOMEPAGE_AFTER_CLOSE_DEVELOPMENTS_NO_ADVICE_DISCLOSURE,
        )


__all__ = [
    "HOMEPAGE_AFTER_CLOSE_DEVELOPMENTS_DEFAULT_AS_OF",
    "HOMEPAGE_AFTER_CLOSE_DEVELOPMENTS_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_AFTER_CLOSE_DEVELOPMENTS_SCHEMA_VERSION",
    "HomepageAfterCloseDevelopmentsService",
]
