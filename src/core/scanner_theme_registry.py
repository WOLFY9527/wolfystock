# -*- coding: utf-8 -*-
"""Curated scanner theme universes."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ScannerTheme:
    id: str
    label_zh: str
    label_en: str
    market: str
    description: str
    symbols: Tuple[str, ...]
    aliases: Tuple[str, ...] = ()
    tags: Tuple[str, ...] = ()
    source: str = "curated_seed"
    version: str = "2026-05-01"
    is_seed_list: bool = True
    requires_manual_maintenance: bool = False

    def to_dict(self) -> Dict[str, object]:
        payload = asdict(self)
        payload["symbols"] = list(self.symbols)
        payload["aliases"] = list(self.aliases)
        payload["tags"] = list(self.tags)
        return payload


# Product note: these are static seed lists. Future user-owned or AI-generated
# theme discovery belongs in a separate custom theme builder, not endless
# hardcoded additions to this registry.
SCANNER_THEMES: Tuple[ScannerTheme, ...] = (
    ScannerTheme(
        id="crypto_miners",
        label_zh="加密矿企",
        label_en="Crypto miners",
        market="us",
        description="US-listed crypto mining and adjacent mining infrastructure seed list; not an authoritative industry classification.",
        symbols=("MARA", "RIOT", "CLSK", "IREN", "CIFR", "HUT", "BTDR", "WULF", "CORZ", "BITF", "HIVE"),
        aliases=("bitcoin miners", "crypto mining"),
        tags=("crypto", "miners", "us"),
    ),
    ScannerTheme(
        id="memory_storage",
        label_zh="存储/硬盘",
        label_en="Memory / storage",
        market="us",
        description="US-listed memory, storage and hard-disk related seed list; not an authoritative industry classification.",
        symbols=("MU", "WDC", "STX", "NTAP", "PSTG"),
        aliases=("memory", "storage", "hard disk"),
        tags=("memory", "storage", "us"),
    ),
    ScannerTheme(
        id="optical_networking",
        label_zh="光通信/网络",
        label_en="Optical networking",
        market="us",
        description="US-listed optical networking, components and datacenter networking seed list.",
        symbols=("CIEN", "LITE", "COHR", "AAOI", "FN", "ANET", "GLW"),
        aliases=("optical networking", "cpo", "datacenter networking"),
        tags=("optical", "networking", "us"),
    ),
    ScannerTheme(
        id="ai_semiconductors",
        label_zh="AI 半导体",
        label_en="AI semiconductors",
        market="us",
        description="US-listed AI semiconductor and semiconductor capital-equipment seed list.",
        symbols=("NVDA", "AMD", "AVGO", "MRVL", "ARM", "TSM", "ASML", "AMAT", "LRCX", "KLAC"),
        aliases=("ai chips", "semiconductors"),
        tags=("ai", "semiconductors", "us"),
    ),
    ScannerTheme(
        id="liquid_cooling_power",
        label_zh="液冷/电力",
        label_en="Liquid cooling / power",
        market="us",
        description="US-listed datacenter cooling, power and thermal infrastructure seed list.",
        symbols=("VRT", "ETN", "PWR", "MOD", "TT", "JCI", "CARR", "SMCI"),
        aliases=("liquid cooling", "datacenter power", "thermal infrastructure"),
        tags=("cooling", "power", "us"),
    ),
    ScannerTheme(
        id="data_center_infra",
        label_zh="数据中心基础设施",
        label_en="Data center infrastructure",
        market="us",
        description="US-listed datacenter infrastructure, power, REIT, server and networking seed list.",
        symbols=("VRT", "ETN", "PWR", "DLR", "EQIX", "SMCI", "ANET", "NTAP"),
        aliases=("data center", "datacenter infrastructure"),
        tags=("datacenter", "infrastructure", "us"),
    ),
    ScannerTheme(
        id="robotics_automation",
        label_zh="机器人/自动化",
        label_en="Robotics / automation",
        market="us",
        description="US-listed robotics, automation and industrial automation seed list.",
        symbols=("ISRG", "TER", "SYM", "PATH", "ROK", "ABBNY", "HON"),
        aliases=("robotics", "automation"),
        tags=("robotics", "automation", "us"),
    ),
    ScannerTheme(
        id="cybersecurity",
        label_zh="网络安全",
        label_en="Cybersecurity",
        market="us",
        description="US-listed cybersecurity software and cloud security seed list.",
        symbols=("CRWD", "PANW", "ZS", "FTNT", "NET", "OKTA", "S"),
        aliases=("security software", "cloud security"),
        tags=("cybersecurity", "software", "us"),
    ),
    ScannerTheme(
        id="quantum",
        label_zh="量子计算",
        label_en="Quantum",
        market="us",
        description="US-listed quantum computing and related seed list.",
        symbols=("IONQ", "RGTI", "QBTS", "QUBT", "ARQQ"),
        aliases=("quantum computing",),
        tags=("quantum", "us"),
    ),
    ScannerTheme(
        id="defense_aerospace",
        label_zh="国防/航空航天",
        label_en="Defense / aerospace",
        market="us",
        description="US-listed defense, aerospace and defense-software seed list.",
        symbols=("LMT", "RTX", "NOC", "GD", "BA", "KTOS", "PLTR"),
        aliases=("defense", "aerospace"),
        tags=("defense", "aerospace", "us"),
    ),
    ScannerTheme(
        id="nuclear_uranium",
        label_zh="核能/铀",
        label_en="Nuclear / uranium",
        market="us",
        description="US-listed uranium, nuclear energy and advanced reactor seed list.",
        symbols=("CCJ", "UEC", "LEU", "SMR", "OKLO", "BWXT"),
        aliases=("nuclear", "uranium"),
        tags=("nuclear", "uranium", "us"),
    ),
    ScannerTheme(
        id="weight_loss_glp1",
        label_zh="减重/GLP-1",
        label_en="Weight loss / GLP-1",
        market="us",
        description="US-listed and US-traded GLP-1 obesity drug seed list.",
        symbols=("LLY", "NVO", "VKTX", "AMGN", "PFE"),
        aliases=("glp-1", "weight loss", "obesity drugs"),
        tags=("healthcare", "glp1", "us"),
    ),
    ScannerTheme(
        id="cloud_ai_software",
        label_zh="云/AI 软件",
        label_en="Cloud AI software",
        market="us",
        description="US-listed cloud, AI platform and data software seed list.",
        symbols=("MSFT", "GOOGL", "AMZN", "META", "NOW", "SNOW", "DDOG", "MDB", "PLTR"),
        aliases=("cloud ai", "data software", "ai software"),
        tags=("cloud", "ai", "software", "us"),
    ),
)

_CN_HK_PLACEHOLDER_THEMES: Tuple[Tuple[str, str, str, str, Tuple[str, ...], Tuple[str, ...]], ...] = (
    ("optical_module_cpo", "光模块 CPO", "Optical module / CPO", "optical module / CPO", ("cpo", "optical modules"), ("optical", "cpo")),
    ("liquid_cooling", "液冷", "Liquid cooling", "liquid cooling", ("liquid cooling",), ("cooling",)),
    ("compute_leasing", "算力租赁", "Compute leasing", "compute leasing", ("compute leasing",), ("compute",)),
    ("memory_storage", "存储", "Memory / storage", "memory / storage", ("memory", "storage"), ("memory", "storage")),
    ("semiconductor_equipment", "半导体设备", "Semiconductor equipment", "semiconductor equipment", ("semiconductor equipment",), ("semiconductor", "equipment")),
    ("robotics", "机器人", "Robotics", "robotics", ("robotics",), ("robotics",)),
    ("ai_chip", "AI 芯片", "AI chip", "AI chip", ("ai chip",), ("ai", "chip")),
    ("data_center_power", "数据中心电源", "Data center power", "data center power", ("data center power",), ("datacenter", "power")),
    ("low_altitude_economy", "低空经济", "Low-altitude economy", "low-altitude economy", ("low altitude economy",), ("low-altitude",)),
    ("humanoid_robot", "人形机器人", "Humanoid robot", "humanoid robot", ("humanoid robot",), ("humanoid", "robotics")),
    ("solid_state_battery", "固态电池", "Solid-state battery", "solid-state battery", ("solid state battery",), ("battery",)),
    ("satellite_internet", "卫星互联网", "Satellite internet", "satellite internet", ("satellite internet",), ("satellite",)),
)

SCANNER_THEMES = SCANNER_THEMES + tuple(
    ScannerTheme(
        id=f"{theme_id}_{market}",
        label_zh=label_zh,
        label_en=label_en,
        market=market,
        description=(
            f"{market.upper()} {description_fragment} theme placeholder. Constituents are not configured; "
            "this is a seed slot that requires manual verification before it can run."
        ),
        symbols=(),
        aliases=aliases,
        tags=(*tags, market),
        source="manual_placeholder",
        requires_manual_maintenance=True,
    )
    for market in ("cn", "hk")
    for theme_id, label_zh, label_en, description_fragment, aliases, tags in _CN_HK_PLACEHOLDER_THEMES
)

_THEMES_BY_ID = {theme.id: theme for theme in SCANNER_THEMES}


def list_scanner_themes(*, market: Optional[str] = None) -> List[ScannerTheme]:
    normalized_market = (market or "").strip().lower()
    return [
        theme
        for theme in SCANNER_THEMES
        if not normalized_market or theme.market == normalized_market
    ]


def get_scanner_theme(theme_id: str) -> Optional[ScannerTheme]:
    return _THEMES_BY_ID.get((theme_id or "").strip().lower())
