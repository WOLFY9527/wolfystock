# -*- coding: utf-8 -*-
"""Rotation Theme Registry v2.

Static metadata only. This module must not import providers, read secrets, or
touch runtime state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Mapping, Sequence


ROTATION_THEME_REGISTRY_VERSION = "rotation_theme_registry_v2"


@dataclass(frozen=True)
class RotationThemeDefinition:
    theme_id: str
    display_name: str
    definition: str
    category: str
    primary_symbols: Sequence[str]
    secondary_symbols: Sequence[str] = field(default_factory=tuple)
    related_symbols: Sequence[str] = field(default_factory=tuple)
    proxy_etfs: Sequence[str] = field(default_factory=tuple)
    proxy_indices: Sequence[str] = field(default_factory=tuple)
    benchmark_symbols: Sequence[str] = field(default_factory=tuple)
    inclusion_notes: Mapping[str, str] = field(default_factory=dict)
    data_quality_notes: Sequence[str] = field(default_factory=tuple)
    aliases: Sequence[str] = field(default_factory=tuple)
    market: str = "US"
    taxonomy_type: str = "theme_cluster"
    data_coverage: str = "quote_backed"
    source_class: str = "curated_theme_registry"
    risk_note: str = "仅作分类观察，不代表实时买卖信号。"
    operator_note: str = "主题注册表 v2；使用 ETF proxy 与相对强弱 proxy，不冒充真实资金流。"

    def all_constituent_symbols(self) -> tuple[str, ...]:
        values = tuple(dict.fromkeys((*self.primary_symbols, *self.secondary_symbols, *self.related_symbols)))
        return values

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["primary_symbols"] = list(self.primary_symbols)
        payload["secondary_symbols"] = list(self.secondary_symbols)
        payload["related_symbols"] = list(self.related_symbols)
        payload["proxy_etfs"] = list(self.proxy_etfs)
        payload["proxy_indices"] = list(self.proxy_indices)
        payload["benchmark_symbols"] = list(self.benchmark_symbols)
        payload["inclusion_notes"] = dict(self.inclusion_notes)
        payload["data_quality_notes"] = list(self.data_quality_notes)
        payload["aliases"] = list(self.aliases)
        return payload


def _theme(
    theme_id: str,
    display_name: str,
    definition: str,
    category: str,
    *,
    primary_symbols: Sequence[str],
    secondary_symbols: Sequence[str] = (),
    related_symbols: Sequence[str] = (),
    proxy_etfs: Sequence[str] = (),
    proxy_indices: Sequence[str] = (),
    benchmark_symbols: Sequence[str] = (),
    inclusion_notes: Mapping[str, str] | None = None,
    data_quality_notes: Sequence[str] = (),
    aliases: Sequence[str] = (),
    data_coverage: str = "quote_backed",
    source_class: str = "curated_theme_registry",
) -> RotationThemeDefinition:
    return RotationThemeDefinition(
        theme_id=theme_id,
        display_name=display_name,
        definition=definition,
        category=category,
        primary_symbols=tuple(primary_symbols),
        secondary_symbols=tuple(secondary_symbols),
        related_symbols=tuple(related_symbols),
        proxy_etfs=tuple(proxy_etfs),
        proxy_indices=tuple(proxy_indices),
        benchmark_symbols=tuple(benchmark_symbols),
        inclusion_notes=dict(inclusion_notes or {}),
        data_quality_notes=tuple(data_quality_notes),
        aliases=tuple(aliases),
        data_coverage=data_coverage,
        source_class=source_class,
    )


_DATA_QUALITY_NOTE = (
    "Proxy ETFs are relative-strength proxies only; no real fund-flow dollars are inferred.",
)

_US_THEME_DEFINITIONS: tuple[RotationThemeDefinition, ...] = (
    _theme(
        "ai_applications",
        "AI 应用",
        "Enterprise software, copilots, and workflow automation names that sit above the compute stack.",
        "AI Applications",
        primary_symbols=("APP", "PLTR", "CRM", "SNOW", "ADBE", "NOW", "DUOL", "MDB"),
        secondary_symbols=("TEAM", "WDAY"),
        proxy_etfs=("IGV",),
        benchmark_symbols=("QQQ", "IGV"),
        data_quality_notes=(
            *_DATA_QUALITY_NOTE,
            "IGV is the software proxy; it is not a claim of direct fund-flow dollars.",
        ),
        aliases=("enterprise ai", "ai software"),
    ),
    _theme(
        "ai_infrastructure",
        "AI 基建",
        "GPU, networking, racks, power, and datacenter buildout names that enable AI infrastructure.",
        "AI Infrastructure",
        primary_symbols=("NVDA", "AVGO", "AMD", "ANET", "SMCI", "DELL", "VRT", "ARM"),
        secondary_symbols=("ORCL", "HPE"),
        proxy_etfs=("SMH", "SOXX"),
        proxy_indices=("SOX",),
        benchmark_symbols=("QQQ", "SMH", "SOXX"),
        inclusion_notes={
            "ORCL": "Oracle is included as an OCI and datacenter-capacity adjacent AI infrastructure proxy, not a pure application-layer name.",
        },
        data_quality_notes=(
            *_DATA_QUALITY_NOTE,
            "SOX is an index concept only; SMH and SOXX are the ETF proxies.",
        ),
        aliases=("ai servers", "gpu infrastructure"),
    ),
    _theme(
        "ai_neocloud",
        "AI 算力云",
        "Neocloud, AI compute cloud, colocation, and hosted GPU capacity names used as AI compute capacity proxies.",
        "AI Compute",
        primary_symbols=("ORCL", "CRWV", "NBIS", "IREN", "CORZ", "CIFR", "WULF", "BTDR"),
        secondary_symbols=("SMCI", "DELL", "HPE", "VRT", "ANET"),
        proxy_etfs=("CLOU", "IGV"),
        benchmark_symbols=("QQQ", "CLOU", "IGV"),
        inclusion_notes={
            "ORCL": "Oracle is included for AI cloud and OCI capacity exposure; it is a neocloud-adjacent AI compute proxy, not a pure software-only name.",
        },
        data_quality_notes=(
            *_DATA_QUALITY_NOTE,
            "CLOU and IGV are ETF proxies for cloud/software participation; no real fund-flow dollars are inferred.",
        ),
        aliases=("ai compute cloud", "neocloud", "gpu cloud"),
    ),
    _theme(
        "semiconductors",
        "半导体",
        "Chip design, foundry, memory, and advanced silicon exposure across the core semiconductor stack.",
        "Semiconductors",
        primary_symbols=("NVDA", "AMD", "AVGO", "TSM", "ASML", "MRVL", "MU", "QCOM"),
        secondary_symbols=("INTC", "TXN", "ARM"),
        proxy_etfs=("SMH", "SOXX"),
        proxy_indices=("SOX",),
        benchmark_symbols=("QQQ", "SMH", "SOXX"),
        data_quality_notes=(
            *_DATA_QUALITY_NOTE,
            "SOX is treated as an index concept; use SMH and SOXX as ETF proxies.",
        ),
        aliases=("chips", "semis"),
    ),
    _theme(
        "semiconductor_equipment",
        "半导体设备",
        "Wafer fabrication equipment, lithography, inspection, metrology, and testing suppliers.",
        "Semiconductor Equipment",
        primary_symbols=("ASML", "AMAT", "LRCX", "KLAC", "TER", "ONTO", "ACLS", "AEHR"),
        secondary_symbols=("ADI", "NXPI"),
        proxy_etfs=("SMH", "SOXX"),
        proxy_indices=("SOX",),
        benchmark_symbols=("QQQ", "SMH", "SOXX"),
        data_quality_notes=(
            *_DATA_QUALITY_NOTE,
            "SOX remains an index concept only; no ETF label should be attached to it.",
        ),
        aliases=("semi equipment", "chip equipment"),
    ),
    _theme(
        "cloud_software",
        "云软件",
        "SaaS, observability, workflow, and cloud application names with platform or enterprise software exposure.",
        "Cloud Software",
        primary_symbols=("MSFT", "CRM", "NOW", "SNOW", "DDOG", "MDB", "TEAM", "WDAY"),
        secondary_symbols=("ORCL", "ADSK"),
        proxy_etfs=("IGV", "CLOU"),
        benchmark_symbols=("QQQ", "IGV", "CLOU"),
        inclusion_notes={
            "ORCL": "Oracle is included for OCI and enterprise cloud adjacency; it is a cloud infrastructure proxy, not a real fund-flow label.",
        },
        data_quality_notes=(
            *_DATA_QUALITY_NOTE,
            "IGV and CLOU are the software/cloud proxies; they are not real fund-flow measures.",
        ),
        aliases=("saas", "cloud"),
    ),
    _theme(
        "cybersecurity",
        "网络安全",
        "Zero trust, endpoint, cloud security, and identity names across the security software stack.",
        "Cybersecurity",
        primary_symbols=("CRWD", "PANW", "ZS", "NET", "FTNT", "OKTA", "S", "TENB"),
        secondary_symbols=("MNDT", "QLYS"),
        proxy_etfs=("CIBR", "HACK"),
        benchmark_symbols=("QQQ", "CIBR", "HACK"),
        data_quality_notes=_DATA_QUALITY_NOTE,
        aliases=("security software", "cloud security"),
    ),
    _theme(
        "crypto_exchanges_brokers",
        "加密交易所 / 券商",
        "Exchanges, brokers, trading platforms, and consumer finance names with crypto-beta exposure.",
        "Crypto Exchanges / Brokers",
        primary_symbols=("COIN", "HOOD", "IBKR", "CME", "GLXY", "BKKT", "SOFI", "PYPL"),
        secondary_symbols=("SQ", "MSTR"),
        proxy_etfs=("BLOK", "BITQ"),
        benchmark_symbols=("QQQ", "BLOK", "BITQ"),
        data_quality_notes=(
            *_DATA_QUALITY_NOTE,
            "BLOK and BITQ are ETF proxies only; they do not imply real fund-flow dollars.",
        ),
        aliases=("exchanges", "brokers"),
        data_coverage="proxy_backed",
        source_class="etf_proxy",
    ),
    _theme(
        "bitcoin_treasury",
        "比特币 Treasury",
        "Equities that explicitly hold or lean into bitcoin treasury exposure and BTC beta.",
        "Bitcoin Treasury",
        primary_symbols=("MSTR", "SMLR", "BTBT", "MARA", "RIOT", "CLSK", "HIVE", "WULF"),
        secondary_symbols=("BTDR", "CORZ"),
        proxy_etfs=("BITO", "WGMI", "BLOK"),
        proxy_indices=("BTC",),
        benchmark_symbols=("QQQ", "BITO", "WGMI", "BLOK"),
        data_quality_notes=(
            *_DATA_QUALITY_NOTE,
            "BTC is an index/asset concept here; BITO, WGMI, and BLOK are the ETF proxies.",
        ),
        aliases=("bitcoin treasury", "btc beta equities"),
        data_coverage="proxy_backed",
        source_class="etf_proxy",
    ),
    _theme(
        "ethereum_treasury",
        "以太坊 Treasury",
        "ETH treasury equities and Ethereum beta names with explicit treasury or ETH-adjacent exposure.",
        "Ethereum Treasury",
        primary_symbols=("BMNR", "SBET", "BTCS", "ETHZ", "MSTR", "CRCL"),
        secondary_symbols=("BTDR",),
        proxy_etfs=("ETHA", "ETHE", "FETH"),
        proxy_indices=("ETH",),
        benchmark_symbols=("QQQ", "ETHA", "ETHE", "FETH"),
        inclusion_notes={
            "BMNR": "BitMine is included as an Ethereum treasury / ETH beta equity with explicit treasury exposure; it is a proxy for ETH beta equities, not a claim of real fund-flow dollars.",
        },
        data_quality_notes=(
            *_DATA_QUALITY_NOTE,
            "ETH is treated as an asset/index concept; ETHA, ETHE, and FETH are the ETF proxies.",
        ),
        aliases=("ethereum treasury", "eth beta"),
        data_coverage="proxy_backed",
        source_class="etf_proxy",
    ),
    _theme(
        "crypto_miners",
        "加密矿企",
        "Bitcoin mining and adjacent mining infrastructure names with operating leverage to BTC beta.",
        "Crypto Miners",
        primary_symbols=("MARA", "RIOT", "CLSK", "IREN", "CIFR", "HUT", "BTDR", "WULF"),
        secondary_symbols=("CORZ", "BITF", "HIVE"),
        proxy_etfs=("WGMI", "BLOK", "BITQ"),
        proxy_indices=("BTC",),
        benchmark_symbols=("QQQ", "WGMI", "BLOK", "BITQ"),
        data_quality_notes=(
            *_DATA_QUALITY_NOTE,
            "BTC is the index concept; WGMI, BLOK, and BITQ are the ETF proxies.",
        ),
        aliases=("bitcoin miners", "crypto mining"),
        data_coverage="proxy_backed",
        source_class="etf_proxy",
    ),
    _theme(
        "stablecoin_tokenization",
        "稳定币 / Tokenization",
        "Stablecoin rails, payment infrastructure, and tokenization-adjacent names with fintech optionality.",
        "Stablecoin / Tokenization",
        primary_symbols=("CRCL", "COIN", "HOOD", "PYPL", "SQ", "V", "MA", "SOFI"),
        secondary_symbols=("NU", "AFRM"),
        proxy_etfs=("FINX", "BLOK"),
        proxy_indices=("USDT", "USDC"),
        benchmark_symbols=("QQQ", "FINX", "BLOK"),
        data_quality_notes=(
            *_DATA_QUALITY_NOTE,
            "USDT and USDC are index/asset concepts here; FINX and BLOK are the ETF proxies.",
        ),
        aliases=("stablecoin", "tokenization"),
        data_coverage="proxy_backed",
        source_class="etf_proxy",
    ),
    _theme(
        "data_center_power",
        "数据中心电力",
        "Power, grid, and electrical infrastructure names used by datacenter buildout and AI load growth.",
        "Data Center Power",
        primary_symbols=("VRT", "ETN", "PWR", "GEV", "CEG", "NRG", "SMR", "AEP"),
        proxy_etfs=("PAVE",),
        benchmark_symbols=("QQQ", "PAVE"),
        data_quality_notes=_DATA_QUALITY_NOTE,
        aliases=("datacenter power", "power infrastructure"),
    ),
    _theme(
        "liquid_cooling",
        "液冷散热",
        "Liquid cooling, thermal management, and high-density rack names tied to datacenter cooling demand.",
        "Liquid Cooling",
        primary_symbols=("VRT", "MOD", "SMCI", "DELL", "HPE", "ANET", "NVDA", "ETN"),
        proxy_etfs=("SMH", "PAVE"),
        benchmark_symbols=("QQQ", "SMH", "PAVE"),
        data_quality_notes=_DATA_QUALITY_NOTE,
        aliases=("cooling", "thermal management"),
    ),
    _theme(
        "robotics",
        "机器人",
        "Industrial automation, machine vision, and robotics names across medical and factory automation.",
        "Robotics",
        primary_symbols=("ISRG", "TER", "SYM", "PATH", "ROK", "ABBNY", "IRBT", "ZBRA"),
        proxy_etfs=("BOTZ",),
        benchmark_symbols=("QQQ", "BOTZ"),
        data_quality_notes=_DATA_QUALITY_NOTE,
        aliases=("automation", "industrial robots"),
    ),
    _theme(
        "nuclear_power_grid",
        "核电 / 电网",
        "Nuclear, utility, and grid-equipment names with power demand and transmission exposure.",
        "Nuclear / Power Grid",
        primary_symbols=("CEG", "GEV", "SMR", "ETN", "PWR", "NEE", "AEP", "VST"),
        proxy_etfs=("XLU", "PAVE"),
        benchmark_symbols=("QQQ", "XLU", "PAVE"),
        data_quality_notes=_DATA_QUALITY_NOTE,
        aliases=("nuclear", "power grid"),
    ),
    _theme(
        "defense_aerospace",
        "国防航天",
        "Defense primes, aerospace, and space systems names.",
        "Defense / Aerospace",
        primary_symbols=("LMT", "RTX", "NOC", "GD", "BA", "KTOS", "RKLB", "ACHR"),
        proxy_etfs=("ITA",),
        benchmark_symbols=("QQQ", "ITA"),
        data_quality_notes=_DATA_QUALITY_NOTE,
        aliases=("defense", "aerospace"),
    ),
    _theme(
        "healthcare_biotech",
        "医疗 / 生物科技",
        "Healthcare, biotech, medtech, and services names with selective innovation exposure.",
        "Healthcare / Biotech",
        primary_symbols=("LLY", "UNH", "ISRG", "REGN", "VRTX", "MRNA", "TMO", "DHR"),
        proxy_etfs=("XLV", "IBB"),
        benchmark_symbols=("QQQ", "XLV", "IBB"),
        data_quality_notes=_DATA_QUALITY_NOTE,
        aliases=("biotech", "healthcare"),
    ),
    _theme(
        "fintech",
        "金融科技",
        "Payments, brokerage, and digital finance names with platform and consumer finance exposure.",
        "Fintech",
        primary_symbols=("V", "MA", "PYPL", "SQ", "COIN", "HOOD", "AFRM", "SOFI"),
        proxy_etfs=("FINX", "XLF"),
        benchmark_symbols=("QQQ", "FINX", "XLF"),
        data_quality_notes=_DATA_QUALITY_NOTE,
        aliases=("payments", "digital finance"),
    ),
    _theme(
        "consumer_internet",
        "消费者互联网",
        "Platforms, streaming, online marketplace, and digital consumer engagement names.",
        "Consumer Internet",
        primary_symbols=("META", "GOOGL", "AMZN", "NFLX", "UBER", "ABNB", "DASH", "SPOT"),
        proxy_etfs=("XLC", "XLY"),
        benchmark_symbols=("QQQ", "XLC", "XLY"),
        data_quality_notes=_DATA_QUALITY_NOTE,
        aliases=("platforms", "internet"),
    ),
    _theme(
        "energy",
        "能源",
        "Oil, gas, LNG, and services names across the energy value chain.",
        "Energy",
        primary_symbols=("XOM", "CVX", "COP", "SLB", "EOG", "LNG", "OXY", "HAL"),
        proxy_etfs=("XLE",),
        benchmark_symbols=("QQQ", "XLE"),
        data_quality_notes=_DATA_QUALITY_NOTE,
        aliases=("oil", "gas"),
    ),
    _theme(
        "industrials",
        "工业",
        "Machinery, transport, and automation names across the industrial stack.",
        "Industrials",
        primary_symbols=("CAT", "DE", "HON", "GE", "UNP", "UPS", "PH", "EMR"),
        proxy_etfs=("XLI",),
        benchmark_symbols=("QQQ", "XLI"),
        data_quality_notes=_DATA_QUALITY_NOTE,
        aliases=("industrial", "manufacturing"),
    ),
    _theme(
        "infrastructure",
        "基础设施",
        "Construction, materials, and infrastructure-capex names tied to grid and industrial buildout.",
        "Infrastructure",
        primary_symbols=("PWR", "VMC", "MLM", "URI", "J", "ACM", "FLR", "ETN"),
        proxy_etfs=("PAVE",),
        benchmark_symbols=("QQQ", "PAVE"),
        data_quality_notes=_DATA_QUALITY_NOTE,
        aliases=("construction", "capex"),
    ),
    _theme(
        "copper_metals",
        "铜 / 金属",
        "Copper, miners, steel, and metals names that express commodity and industrial cycle exposure.",
        "Copper / Metals",
        primary_symbols=("FCX", "SCCO", "TECK", "RIO", "BHP", "AA", "CLF", "X"),
        proxy_etfs=("COPX", "XME"),
        benchmark_symbols=("QQQ", "COPX", "XME"),
        data_quality_notes=_DATA_QUALITY_NOTE,
        aliases=("copper", "metals"),
    ),
    _theme(
        "small_cap_growth",
        "小盘成长",
        "Small-cap growth names used to read risk appetite and breadth across the broader tape.",
        "Small-cap Growth",
        primary_symbols=("IWM", "RVTY", "FOUR", "TMDX", "SFM", "CELH", "DUOL", "PATH"),
        proxy_etfs=("IWM", "IWO"),
        benchmark_symbols=("IWM", "IWO"),
        data_quality_notes=_DATA_QUALITY_NOTE,
        aliases=("small cap", "growth factor"),
        data_coverage="proxy_backed",
        source_class="etf_proxy",
    ),
    _theme(
        "utilities",
        "公用事业",
        "Regulated utilities and power demand names used for defensive and rate-sensitive exposure.",
        "Utilities",
        primary_symbols=("NEE", "SO", "DUK", "AEP", "EXC", "SRE", "PEG", "VST"),
        proxy_etfs=("XLU",),
        benchmark_symbols=("QQQ", "XLU"),
        data_quality_notes=_DATA_QUALITY_NOTE,
        aliases=("utility", "defensive"),
    ),
    _theme(
        "materials",
        "材料",
        "Chemicals, gold miners, steel, and materials names tied to industrial and commodity cycles.",
        "Materials",
        primary_symbols=("LIN", "APD", "SHW", "ECL", "NEM", "DD", "DOW", "NUE"),
        proxy_etfs=("XLB",),
        benchmark_symbols=("QQQ", "XLB"),
        data_quality_notes=_DATA_QUALITY_NOTE,
        aliases=("materials", "chemicals"),
    ),
)

_US_THEMES_BY_ID = {theme.theme_id: theme for theme in _US_THEME_DEFINITIONS}


def normalize_rotation_theme_market(market: str | None) -> str:
    raw = str(market or "US").strip().upper()
    aliases = {
        "USA": "US",
        "UNITED STATES": "US",
        "US": "US",
    }
    return aliases.get(raw, raw)


def get_rotation_theme_definition(theme_id: str) -> RotationThemeDefinition | None:
    return _US_THEMES_BY_ID.get(str(theme_id or "").strip())


def list_rotation_theme_definitions(market: str | None = "US") -> tuple[RotationThemeDefinition, ...]:
    return _US_THEME_DEFINITIONS if normalize_rotation_theme_market(market) == "US" else ()


def list_rotation_theme_ids(market: str | None = "US") -> tuple[str, ...]:
    return tuple(theme.theme_id for theme in list_rotation_theme_definitions(market))


def list_rotation_theme_proxy_etfs(market: str | None = "US") -> tuple[str, ...]:
    if normalize_rotation_theme_market(market) != "US":
        return ()
    return tuple(
        dict.fromkeys(
            proxy
            for theme in _US_THEME_DEFINITIONS
            for proxy in theme.proxy_etfs
        )
    )
