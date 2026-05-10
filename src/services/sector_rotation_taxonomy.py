# -*- coding: utf-8 -*-
"""Inert multi-market taxonomy entries for the rotation radar.

This module is static metadata only. It must not import provider clients, read
credentials, inspect environment variables, or call networks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence


SUPPORTED_ROTATION_MARKETS = ("US", "CN", "HK", "CRYPTO")
ROTATION_TAXONOMY_VERSION = "sector_rotation_taxonomy_v1"


@dataclass(frozen=True)
class RotationTaxonomyEntry:
    market: str
    taxonomyType: str
    id: str
    displayName: str
    englishName: str = ""
    aliases: Sequence[str] = field(default_factory=tuple)
    representativeSymbols: Sequence[str] = field(default_factory=tuple)
    representativeLabels: Sequence[str] = field(default_factory=tuple)
    proxySymbols: Sequence[str] = field(default_factory=tuple)
    children: Sequence[str] = field(default_factory=tuple)
    mappedConcepts: Sequence[str] = field(default_factory=tuple)
    enabledByDefault: bool = True
    userVisible: bool = True
    dataCoverage: str = "taxonomy_only"
    sourceClass: str = "local_taxonomy"
    riskNote: str = "仅作分类观察，不代表实时买卖信号。"
    operatorNote: str = "静态主题库，本地行情覆盖后可计算轮动强度。"


def _entry(
    market: str,
    slug: str,
    name: str,
    english: str,
    *,
    taxonomy_type: str = "theme_cluster",
    aliases: Sequence[str] = (),
    symbols: Sequence[str] = (),
    labels: Sequence[str] = (),
    proxies: Sequence[str] = (),
    concepts: Sequence[str] = (),
    coverage: str = "taxonomy_only",
    source_class: str = "local_taxonomy",
) -> RotationTaxonomyEntry:
    return RotationTaxonomyEntry(
        market=market,
        taxonomyType=taxonomy_type,
        id=f"{market}:{taxonomy_type}:{slug}",
        displayName=name,
        englishName=english,
        aliases=tuple(aliases),
        representativeSymbols=tuple(symbols),
        representativeLabels=tuple(labels),
        proxySymbols=tuple(proxies),
        mappedConcepts=tuple(concepts or aliases),
        dataCoverage=coverage,
        sourceClass=source_class,
    )


_US_ENTRIES: tuple[RotationTaxonomyEntry, ...] = (
    _entry("US", "ai_applications", "AI 应用", "AI Applications", symbols=("APP", "PLTR", "CRM", "SNOW", "ADBE", "NOW", "DUOL", "MDB"), proxies=("QQQ", "IGV"), concepts=("enterprise AI", "data workflow", "AI agents"), coverage="quote_backed", source_class="custom"),
    _entry("US", "ai_infrastructure", "AI 基建", "AI Infrastructure", symbols=("NVDA", "AVGO", "AMD", "ANET", "SMCI", "DELL", "VRT", "ARM"), proxies=("QQQ", "SMH"), concepts=("GPU", "AI servers", "networking"), coverage="quote_backed", source_class="custom"),
    _entry("US", "semiconductors", "半导体", "Semiconductors", symbols=("NVDA", "AMD", "AVGO", "TSM", "ASML", "MRVL", "MU", "LRCX"), proxies=("SMH",), concepts=("chip design", "foundry", "memory"), coverage="quote_backed", source_class="custom"),
    _entry("US", "semiconductor_equipment", "半导体设备", "Semiconductor Equipment", symbols=("ASML", "AMAT", "LRCX", "KLAC", "TER", "ONTO", "ACLS", "AEHR"), proxies=("SMH",), concepts=("wafer equipment", "metrology", "testing"), coverage="quote_backed", source_class="custom"),
    _entry("US", "cybersecurity", "网络安全", "Cybersecurity", symbols=("CRWD", "PANW", "ZS", "NET", "FTNT", "S", "OKTA", "TENB"), proxies=("CIBR",), concepts=("zero trust", "cloud security", "endpoint security"), coverage="quote_backed", source_class="custom"),
    _entry("US", "cloud_software", "云软件", "Cloud Software", symbols=("MSFT", "SNOW", "CRM", "NOW", "DDOG", "MDB", "TEAM", "WDAY"), proxies=("CLOU", "IGV"), concepts=("SaaS", "observability", "workflow software"), coverage="quote_backed", source_class="custom"),
    _entry("US", "data_center_power", "数据中心电力", "Data Center Power", symbols=("VRT", "ETN", "PWR", "GEV", "CEG", "NRG", "SMR", "AEP"), proxies=("PAVE",), concepts=("power grid", "generators", "electrification"), coverage="quote_backed", source_class="custom"),
    _entry("US", "liquid_cooling", "液冷散热", "Liquid Cooling", symbols=("VRT", "MOD", "SMCI", "DELL", "HPE", "ANET", "NVDA", "ETN"), proxies=("SMH", "PAVE"), concepts=("thermal management", "high-density racks"), coverage="quote_backed", source_class="custom"),
    _entry("US", "robotics", "机器人", "Robotics", symbols=("ISRG", "TER", "SYM", "PATH", "ROK", "ABBNY", "IRBT", "ZBRA"), proxies=("BOTZ",), concepts=("industrial automation", "surgical robotics", "machine vision"), coverage="quote_backed", source_class="custom"),
    _entry("US", "nuclear_power_grid", "核电 / 电网", "Nuclear / Power Grid", symbols=("CEG", "GEV", "SMR", "ETN", "PWR", "NEE", "AEP", "VST"), proxies=("XLU", "PAVE"), concepts=("nuclear", "grid equipment", "utilities"), coverage="quote_backed", source_class="custom"),
    _entry("US", "defense_aerospace", "国防航天", "Defense / Aerospace", symbols=("LMT", "RTX", "NOC", "GD", "BA", "KTOS", "RKLB", "ACHR"), proxies=("ITA",), concepts=("defense primes", "space", "drones"), coverage="quote_backed", source_class="custom"),
    _entry("US", "healthcare_biotech", "医疗 / 生物科技", "Healthcare / Biotech", symbols=("LLY", "UNH", "ISRG", "REGN", "VRTX", "MRNA", "TMO", "DHR"), proxies=("XLV", "IBB"), concepts=("biotech", "medtech", "healthcare services"), coverage="quote_backed", source_class="custom"),
    _entry("US", "fintech", "金融科技", "Fintech", symbols=("V", "MA", "PYPL", "SQ", "COIN", "HOOD", "AFRM", "SOFI"), proxies=("FINX", "XLF"), concepts=("payments", "brokerage", "digital finance"), coverage="quote_backed", source_class="custom"),
    _entry("US", "consumer_internet", "消费者互联网", "Consumer Internet", symbols=("META", "GOOGL", "AMZN", "NFLX", "UBER", "ABNB", "DASH", "SPOT"), proxies=("XLC", "XLY"), concepts=("platforms", "streaming", "online marketplaces"), coverage="quote_backed", source_class="custom"),
    _entry("US", "energy", "能源", "Energy", symbols=("XOM", "CVX", "COP", "SLB", "EOG", "LNG", "OXY", "HAL"), proxies=("XLE",), concepts=("oil gas", "services", "LNG"), coverage="quote_backed", source_class="custom"),
    _entry("US", "industrials", "工业", "Industrials", symbols=("CAT", "DE", "HON", "GE", "UNP", "UPS", "PH", "EMR"), proxies=("XLI",), concepts=("machinery", "transport", "automation"), coverage="quote_backed", source_class="custom"),
    _entry("US", "infrastructure", "基础设施", "Infrastructure", symbols=("PWR", "VMC", "MLM", "URI", "J", "ACM", "FLR", "ETN"), proxies=("PAVE",), concepts=("construction", "materials", "grid capex"), coverage="quote_backed", source_class="custom"),
    _entry("US", "copper_metals", "铜 / 金属", "Copper / Metals", symbols=("FCX", "SCCO", "TECK", "RIO", "BHP", "AA", "CLF", "X"), proxies=("COPX", "XME"), concepts=("copper", "miners", "steel"), coverage="quote_backed", source_class="custom"),
    _entry("US", "crypto_blockchain_proxy", "Crypto / Blockchain Proxy", "Crypto / Blockchain Proxy", symbols=("COIN", "MSTR", "MARA", "RIOT", "CLSK", "HOOD", "GLXY", "HUT"), proxies=("BITO", "BLOK"), concepts=("bitcoin miners", "exchanges", "treasury proxies"), coverage="proxy_backed", source_class="etf_proxy"),
    _entry("US", "small_cap_growth", "小盘成长", "Small-cap Growth", symbols=("IWM", "RVTY", "FOUR", "TMDX", "SFM", "CELH", "DUOL", "PATH"), proxies=("IWM", "IWO"), concepts=("small cap", "growth factor", "risk appetite"), coverage="proxy_backed", source_class="etf_proxy"),
    _entry("US", "utilities", "公用事业", "Utilities", symbols=("NEE", "SO", "DUK", "AEP", "EXC", "SRE", "PEG", "VST"), proxies=("XLU",), concepts=("regulated utilities", "power demand"), coverage="quote_backed", source_class="custom"),
    _entry("US", "materials", "材料", "Materials", symbols=("LIN", "APD", "SHW", "ECL", "NEM", "DD", "DOW", "NUE"), proxies=("XLB",), concepts=("chemicals", "gold miners", "materials"), coverage="quote_backed", source_class="custom"),
)


_CN_ENTRIES: tuple[RotationTaxonomyEntry, ...] = (
    _entry("CN", "ai_compute", "AI算力", "AI Compute", labels=("寒武纪", "中科曙光", "工业富联"), concepts=("算力租赁", "GPU供应链", "服务器", "数据中心")),
    _entry("CN", "ai_infra_liquid_cooling", "AI基建 / 液冷散热", "AI Infrastructure / Liquid Cooling", labels=("高澜股份", "英维克", "曙光数创"), concepts=("液冷服务器", "IDC温控", "高密度机柜")),
    _entry("CN", "optical_cpo", "光模块 / CPO", "Optical Modules / CPO", labels=("中际旭创", "新易盛", "天孚通信"), concepts=("光模块", "CPO", "硅光")),
    _entry("CN", "semiconductor_equipment", "半导体设备", "Semiconductor Equipment", labels=("北方华创", "中微公司", "盛美上海"), concepts=("刻蚀", "薄膜沉积", "清洗设备")),
    _entry("CN", "domestic_chips", "国产芯片", "Domestic Chips", labels=("海光信息", "兆易创新", "韦尔股份"), concepts=("AI芯片", "MCU", "模拟芯片")),
    _entry("CN", "memory", "存储", "Memory", labels=("兆易创新", "江波龙", "佰维存储"), concepts=("DRAM", "NAND", "HBM")),
    _entry("CN", "servers_data_center", "服务器 / 数据中心", "Servers / Data Center", labels=("工业富联", "浪潮信息", "紫光股份"), concepts=("服务器", "IDC", "交换机")),
    _entry("CN", "compute_leasing", "算力租赁", "Compute Leasing", labels=("云赛智联", "莲花控股", "润建股份"), concepts=("算力租赁", "智算中心")),
    _entry("CN", "robotics", "机器人", "Robotics", labels=("埃斯顿", "汇川技术", "绿的谐波"), concepts=("人形机器人", "减速器", "伺服系统")),
    _entry("CN", "low_altitude", "低空经济", "Low-altitude Economy", labels=("万丰奥威", "宗申动力", "中信海直"), concepts=("eVTOL", "无人机", "空管系统")),
    _entry("CN", "ev_chain", "新能源车链", "EV Supply Chain", labels=("比亚迪", "宁德时代", "拓普集团"), concepts=("电池", "电驱", "智能驾驶")),
    _entry("CN", "solid_state_battery", "固态电池", "Solid-state Battery", labels=("宁德时代", "赣锋锂业", "当升科技"), concepts=("固态电解质", "锂电材料")),
    _entry("CN", "solar_storage", "光伏 / 储能", "Solar / Energy Storage", labels=("阳光电源", "隆基绿能", "通威股份"), concepts=("光伏组件", "逆变器", "储能")),
    _entry("CN", "power_equipment_uhv", "电力设备 / 特高压", "Power Equipment / UHV", labels=("国电南瑞", "许继电气", "平高电气"), concepts=("特高压", "电网设备", "变压器")),
    _entry("CN", "nuclear_power", "核电", "Nuclear Power", labels=("中国核电", "中核科技", "江苏神通"), concepts=("核电运营", "核级阀门", "核岛设备")),
    _entry("CN", "nonferrous_metals", "有色金属", "Nonferrous Metals", labels=("紫金矿业", "洛阳钼业", "江西铜业"), concepts=("铜", "铝", "贵金属")),
    _entry("CN", "rare_earth_magnets", "稀土永磁", "Rare Earth Magnets", labels=("北方稀土", "金力永磁", "中国稀土"), concepts=("稀土", "永磁材料")),
    _entry("CN", "defense", "军工", "Defense", labels=("中航沈飞", "航发动力", "中航西飞"), concepts=("航空装备", "发动机", "军工电子")),
    _entry("CN", "satellite_internet", "卫星互联网", "Satellite Internet", labels=("中国卫星", "铖昌科技", "海格通信"), concepts=("卫星通信", "低轨卫星")),
    _entry("CN", "vehicle_road_cloud", "车路云", "Vehicle-Road-Cloud", labels=("千方科技", "金溢科技", "万集科技"), concepts=("智能网联", "路侧感知", "车联网")),
    _entry("CN", "consumer_electronics", "消费电子", "Consumer Electronics", labels=("立讯精密", "歌尔股份", "蓝思科技"), concepts=("手机链", "MR", "声学光学")),
    _entry("CN", "huawei_harmony", "华为链 / 鸿蒙生态", "Huawei / HarmonyOS Ecosystem", labels=("软通动力", "润和软件", "中科创达"), concepts=("鸿蒙", "昇腾", "华为供应链")),
    _entry("CN", "xinchuang_software", "信创 / 国产软件", "Xinchuang / Domestic Software", labels=("中国软件", "太极股份", "用友网络"), concepts=("操作系统", "数据库", "办公软件")),
    _entry("CN", "media_games", "传媒游戏", "Media / Games", labels=("三七互娱", "完美世界", "昆仑万维"), concepts=("游戏", "影视", "AIGC内容")),
    _entry("CN", "innovative_drugs", "创新药", "Innovative Drugs", labels=("恒瑞医药", "百济神州", "药明康德"), concepts=("创新药", "CXO", "ADC")),
    _entry("CN", "medical_devices", "医疗器械", "Medical Devices", labels=("迈瑞医疗", "联影医疗", "鱼跃医疗"), concepts=("影像设备", "IVD", "家用器械")),
    _entry("CN", "baijiu_consumption", "白酒消费", "Baijiu / Consumption", labels=("贵州茅台", "五粮液", "泸州老窖"), concepts=("白酒", "食品饮料")),
    _entry("CN", "travel", "旅游出行", "Travel / Mobility", labels=("中国中免", "宋城演艺", "春秋航空"), concepts=("免税", "景区", "航空")),
    _entry("CN", "brokerage_finance", "证券金融", "Brokerage / Finance", labels=("东方财富", "中信证券", "中国平安"), concepts=("券商", "保险", "财富管理")),
    _entry("CN", "coal_resources", "煤炭 / 资源", "Coal / Resources", labels=("中国神华", "陕西煤业", "兖矿能源"), concepts=("煤炭", "资源品", "高股息")),
)


_HK_ENTRIES: tuple[RotationTaxonomyEntry, ...] = (
    _entry("HK", "hk_tech", "港股科技", "HK Technology", symbols=("0700.HK", "9988.HK", "3690.HK"), concepts=("恒生科技", "平台经济"), coverage="taxonomy_only"),
    _entry("HK", "internet_platforms", "互联网平台", "Internet Platforms", symbols=("0700.HK", "9988.HK", "9618.HK"), concepts=("电商", "本地生活", "游戏")),
    _entry("HK", "biotech", "港股生物科技", "HK Biotech", symbols=("2269.HK", "6160.HK", "1801.HK"), concepts=("18A生物科技", "创新药")),
    _entry("HK", "ev", "新能源汽车", "New Energy Vehicles", symbols=("1211.HK", "9866.HK", "2015.HK"), concepts=("整车", "电池", "智能驾驶")),
    _entry("HK", "property", "内房 / 物业", "Property / Property Management", symbols=("0688.HK", "1109.HK", "6098.HK"), concepts=("内房", "物业管理")),
    _entry("HK", "financial_insurance", "金融保险", "Financials / Insurance", symbols=("1299.HK", "2318.HK", "0005.HK"), concepts=("保险", "银行", "券商")),
    _entry("HK", "energy_resources", "能源资源", "Energy / Resources", symbols=("0883.HK", "0857.HK", "1088.HK"), concepts=("石油", "煤炭", "金属")),
    _entry("HK", "consumer_services", "消费服务", "Consumer Services", symbols=("3690.HK", "9961.HK", "2020.HK"), concepts=("餐饮", "出行", "零售")),
    _entry("HK", "telecom", "电讯运营", "Telecom Operators", symbols=("0941.HK", "0728.HK", "0762.HK"), concepts=("运营商", "派息")),
    _entry("HK", "high_dividend", "高股息红利", "High Dividend", symbols=("0005.HK", "0941.HK", "1088.HK"), concepts=("红利", "央企", "防御")),
)


_CRYPTO_ENTRIES: tuple[RotationTaxonomyEntry, ...] = (
    _entry("CRYPTO", "layer_1", "Layer 1", "Layer 1", symbols=("BTC", "ETH", "SOL", "BNB"), concepts=("base chains", "settlement")),
    _entry("CRYPTO", "layer_2", "Layer 2", "Layer 2", symbols=("ARB", "OP", "MATIC"), concepts=("rollups", "scaling")),
    _entry("CRYPTO", "defi", "DeFi", "DeFi", symbols=("UNI", "AAVE", "MKR"), concepts=("DEX", "lending", "stable liquidity")),
    _entry("CRYPTO", "ai_crypto", "AI Crypto", "AI Crypto", symbols=("TAO", "FET", "RNDR"), concepts=("AI networks", "compute marketplaces")),
    _entry("CRYPTO", "exchange_platform", "Exchange / Platform", "Exchange / Platform", symbols=("BNB", "OKB", "COIN"), concepts=("exchanges", "platform tokens")),
    _entry("CRYPTO", "stablecoin_infra", "Stablecoin Infrastructure", "Stablecoin Infrastructure", symbols=("USDT", "USDC", "ENA"), concepts=("stablecoins", "payment rails")),
    _entry("CRYPTO", "bitcoin_ecosystem", "Bitcoin Ecosystem", "Bitcoin Ecosystem", symbols=("BTC", "ORDI", "STX"), concepts=("bitcoin beta", "ordinals", "miners")),
    _entry("CRYPTO", "ethereum_ecosystem", "Ethereum Ecosystem", "Ethereum Ecosystem", symbols=("ETH", "LDO", "ENS"), concepts=("staking", "apps", "identity")),
    _entry("CRYPTO", "depin", "DePIN", "DePIN", symbols=("HNT", "FIL", "AR"), concepts=("decentralized infrastructure", "storage")),
    _entry("CRYPTO", "gaming_metaverse", "Gaming / Metaverse", "Gaming / Metaverse", symbols=("IMX", "SAND", "GALA"), concepts=("gaming", "metaverse", "NFT infrastructure")),
)


_ENTRIES: tuple[RotationTaxonomyEntry, ...] = _US_ENTRIES + _CN_ENTRIES + _HK_ENTRIES + _CRYPTO_ENTRIES


def normalize_rotation_market(market: str | None) -> str:
    raw = str(market or "US").strip().upper()
    aliases = {
        "A": "CN",
        "A股": "CN",
        "CN/A股": "CN",
        "CHINA": "CN",
        "CRYPTO": "CRYPTO",
        "CRYPTOCURRENCY": "CRYPTO",
        "数字货币": "CRYPTO",
    }
    return aliases.get(raw, raw) if aliases.get(raw, raw) in SUPPORTED_ROTATION_MARKETS else "US"


def list_rotation_taxonomy_entries() -> tuple[RotationTaxonomyEntry, ...]:
    return _ENTRIES


def get_rotation_taxonomy_version() -> str:
    return ROTATION_TAXONOMY_VERSION


def get_rotation_taxonomy_by_market(market: str | None) -> tuple[RotationTaxonomyEntry, ...]:
    normalized = normalize_rotation_market(market)
    return tuple(entry for entry in _ENTRIES if entry.market == normalized and entry.enabledByDefault and entry.userVisible)
